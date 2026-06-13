"""Tests for TOTP / MFA enforcement (Item 23).

Covers:

* The pure rule ``is_mfa_required_for_owner(plan, member_count)``.
* The ``require_mfa_if_enforced`` dependency as wired to
  ``POST /api/team/invite`` and ``POST /api/billing/portal``.
* Bypass conditions:
    - Owner on FREE plan with a small team → route reachable.
    - Non-owner members on a PRO org → route's own role guard fires
      (403 "Only owners …"), MFA never evaluates.
* Enforcement fires:
    - Owner on PRO plan without TOTP → 403 MFA_REQUIRED.
    - Owner on FREE plan with ≥ ``MFA_MEMBER_THRESHOLD`` members and no
      TOTP → 403 MFA_REQUIRED.
* Enforcement passes when the owner has ``totp_enabled=True``.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.database import async_session, engine
from app.main import app
from app.middleware.auth import get_current_member
from app.models.auth import AuthUser
from app.models.organization import (
    Organization,
    OrganizationMember,
    OrgPlan,
    OrgRole,
)
from app.services.mfa_enforcement import (
    MFA_MEMBER_THRESHOLD,
    is_mfa_required_for_owner,
)


# --------------------------------------------------------------------------- #
# Pure-function tests — no DB, no HTTP.
# --------------------------------------------------------------------------- #

def test_is_mfa_required_pro_owner_always_true() -> None:
    assert is_mfa_required_for_owner(OrgPlan.PRO, 1) is True
    assert is_mfa_required_for_owner(OrgPlan.PRO, 0) is True


def test_is_mfa_required_enterprise_owner_always_true() -> None:
    assert is_mfa_required_for_owner(OrgPlan.ENTERPRISE, 1) is True


def test_is_mfa_required_free_small_team_is_false() -> None:
    # FREE with 1..threshold-1 members should pass through.
    for n in range(0, MFA_MEMBER_THRESHOLD):
        assert is_mfa_required_for_owner(OrgPlan.FREE, n) is False, (
            f"member_count={n} unexpectedly requires MFA"
        )


def test_is_mfa_required_free_large_team_is_true() -> None:
    assert is_mfa_required_for_owner(OrgPlan.FREE, MFA_MEMBER_THRESHOLD) is True
    assert is_mfa_required_for_owner(OrgPlan.FREE, MFA_MEMBER_THRESHOLD + 10) is True


# --------------------------------------------------------------------------- #
# HTTP tests — require Postgres.
# --------------------------------------------------------------------------- #

async def _postgres_reachable() -> bool:
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest_asyncio.fixture
async def pg_session():
    if not await _postgres_reachable():
        pytest.skip("PostgreSQL not reachable — run `docker compose up db`")
    async with async_session() as session:
        yield session


async def _mk_org(db, plan: OrgPlan, *, extra_members: int = 0) -> tuple[Organization, OrganizationMember, uuid.UUID]:
    """Create an org with a single owner plus ``extra_members`` fillers."""
    org = Organization(
        id=uuid.uuid4(),
        name=f"MFA-{plan.value}-{uuid.uuid4().hex[:6]}",
        org_number=f"556{uuid.uuid4().int % 10**9:09d}"[:10],
        plan=plan,
    )
    owner_user_id = uuid.uuid4()
    owner = OrganizationMember(
        org_id=org.id, user_id=owner_user_id, role=OrgRole.OWNER
    )
    db.add_all([org, owner])
    for _ in range(extra_members):
        db.add(OrganizationMember(
            org_id=org.id, user_id=uuid.uuid4(), role=OrgRole.MEMBER,
        ))
    await db.commit()
    return org, owner, owner_user_id


async def _mk_auth_user(db, user_id: uuid.UUID, *, totp_enabled: bool) -> AuthUser:
    au = AuthUser(
        id=user_id,
        email=f"{user_id}@test.varuflow.local",
        # bcrypt-shaped dummy — hash never verified in these tests.
        hashed_password="$2b$12$" + "x" * 53,
        is_email_verified=True,
        totp_enabled=totp_enabled,
        totp_secret="JBSWY3DPEHPK3PXP" if totp_enabled else None,
    )
    db.add(au)
    await db.commit()
    return au


def _override(member: OrganizationMember):
    async def _o():
        return {"user_id": member.user_id, "email": "test@varuflow.local"}, member
    return _o


async def _cleanup(db, org_id: uuid.UUID, auth_user_ids: list[uuid.UUID]) -> None:
    # auth_users first — no FK from organizations, but we want a clean slate
    for uid in auth_user_ids:
        row = await db.get(AuthUser, uid)
        if row:
            await db.delete(row)
    org = await db.get(Organization, org_id)
    if org:
        await db.delete(org)
    await db.commit()


@pytest.mark.asyncio
async def test_owner_free_small_team_bypasses_mfa(pg_session) -> None:
    """FREE plan + 1 owner → team invite reachable without TOTP."""
    org, owner, owner_uid = await _mk_org(pg_session, OrgPlan.FREE)
    app.dependency_overrides[get_current_member] = _override(owner)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            # Use the billing portal route — easier: it will return 400 for
            # missing Stripe customer, but NOT 403 MFA_REQUIRED. That's what
            # we assert: the MFA gate let it through.
            r = await c.post("/api/billing/portal")
        assert r.status_code != 403 or "MFA_REQUIRED" not in r.text
    finally:
        app.dependency_overrides.pop(get_current_member, None)
        await _cleanup(pg_session, org.id, [])


@pytest.mark.asyncio
async def test_owner_pro_without_totp_blocked(pg_session) -> None:
    """PRO plan owner without TOTP → 403 MFA_REQUIRED on a gated route."""
    org, owner, owner_uid = await _mk_org(pg_session, OrgPlan.PRO)
    await _mk_auth_user(pg_session, owner_uid, totp_enabled=False)
    app.dependency_overrides[get_current_member] = _override(owner)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/billing/portal")
        assert r.status_code == 403
        body = r.json()
        # FastAPI nests the structured detail under "detail"
        assert body["detail"]["code"] == "MFA_REQUIRED"
    finally:
        app.dependency_overrides.pop(get_current_member, None)
        await _cleanup(pg_session, org.id, [owner_uid])


@pytest.mark.asyncio
async def test_owner_pro_with_totp_passes(pg_session) -> None:
    """PRO owner with totp_enabled=True → gate lets the call through."""
    org, owner, owner_uid = await _mk_org(pg_session, OrgPlan.PRO)
    await _mk_auth_user(pg_session, owner_uid, totp_enabled=True)
    app.dependency_overrides[get_current_member] = _override(owner)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/billing/portal")
        # Not 403/MFA_REQUIRED — the gate passed. Downstream 400 "No Stripe
        # customer" is fine and expected in tests.
        if r.status_code == 403:
            assert "MFA_REQUIRED" not in r.text
    finally:
        app.dependency_overrides.pop(get_current_member, None)
        await _cleanup(pg_session, org.id, [owner_uid])


@pytest.mark.asyncio
async def test_owner_free_large_team_blocked(pg_session) -> None:
    """FREE plan + ≥ MFA_MEMBER_THRESHOLD members without TOTP → blocked."""
    org, owner, owner_uid = await _mk_org(
        pg_session, OrgPlan.FREE, extra_members=MFA_MEMBER_THRESHOLD,
    )
    await _mk_auth_user(pg_session, owner_uid, totp_enabled=False)
    app.dependency_overrides[get_current_member] = _override(owner)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/billing/portal")
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "MFA_REQUIRED"
    finally:
        app.dependency_overrides.pop(get_current_member, None)
        await _cleanup(pg_session, org.id, [owner_uid])


@pytest.mark.asyncio
async def test_non_owner_bypasses_mfa_gate(pg_session) -> None:
    """ADMIN on PRO plan hits route's own role guard, not MFA."""
    org, _owner, _owner_uid = await _mk_org(pg_session, OrgPlan.PRO)
    # Add an ADMIN and route the request as them.
    admin_uid = uuid.uuid4()
    admin = OrganizationMember(org_id=org.id, user_id=admin_uid, role=OrgRole.ADMIN)
    pg_session.add(admin)
    await pg_session.commit()
    app.dependency_overrides[get_current_member] = _override(admin)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/billing/portal")
        # Must be 403 from the role guard, never the MFA gate.
        assert r.status_code == 403
        assert "MFA_REQUIRED" not in r.text
    finally:
        app.dependency_overrides.pop(get_current_member, None)
        await _cleanup(pg_session, org.id, [])


@pytest.mark.asyncio
async def test_security_status_reports_enforcement(pg_session) -> None:
    """GET /api/settings/security/status reflects plan + member + TOTP state."""
    org, owner, owner_uid = await _mk_org(pg_session, OrgPlan.PRO)
    await _mk_auth_user(pg_session, owner_uid, totp_enabled=False)
    app.dependency_overrides[get_current_member] = _override(owner)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/settings/security/status")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["plan"] == "PRO"
        assert body["role"] == "OWNER"
        assert body["mfa_required"] is True
        assert body["mfa_enabled"] is False
        assert body["member_threshold"] == MFA_MEMBER_THRESHOLD
    finally:
        app.dependency_overrides.pop(get_current_member, None)
        await _cleanup(pg_session, org.id, [owner_uid])
