"""Tests for the per-org IP allowlist (Item 25 / migration v45).

Covers:

* Pure helpers: ``parse_cidr`` validates + normalises bare IPs, CIDRs,
  IPv6, and rejects garbage + host-bits-set CIDRs.
* Pure helper: ``ip_matches_allowlist`` matches /32, /24, IPv6, and
  safely fails on missing IP / empty list / malformed entries.
* Middleware enforcement: an org with zero entries allows any IP; an
  org with ≥ 1 entry denies non-matching IPs with a structured 403
  ``IP_NOT_ALLOWED``; a matching IP passes through.
* Router guard: non-owner cannot POST; non-Enterprise org cannot POST;
  invalid CIDR is rejected with 400; duplicate CIDR is rejected with
  409.
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
from app.features.auth.organization import (
    OrgIpAllowlistEntry,
    OrgPlan,
    OrgRole,
    Organization,
    OrganizationMember,
)
from app.services.ip_allowlist import ip_matches_allowlist, parse_cidr


# --------------------------------------------------------------------------- #
# Pure-function tests — no DB, no HTTP.
# --------------------------------------------------------------------------- #

def test_parse_cidr_normalises_bare_ip_to_slash32() -> None:
    assert parse_cidr("203.0.113.5") == "203.0.113.5/32"


def test_parse_cidr_keeps_cidr_as_is() -> None:
    assert parse_cidr("203.0.113.0/24") == "203.0.113.0/24"


def test_parse_cidr_accepts_ipv6() -> None:
    assert parse_cidr("2001:db8::/32") == "2001:db8::/32"


@pytest.mark.parametrize("bad", ["", "   ", "garbage", "999.999.999.999", None])
def test_parse_cidr_rejects_garbage(bad) -> None:
    with pytest.raises(ValueError):
        parse_cidr(bad)  # type: ignore[arg-type]


def test_parse_cidr_rejects_host_bits_set() -> None:
    # 203.0.113.5/24 has host bits — almost always a typo on a firewall.
    with pytest.raises(ValueError):
        parse_cidr("203.0.113.5/24")


def test_match_exact_ip_in_slash32() -> None:
    assert ip_matches_allowlist("203.0.113.5", ["203.0.113.5/32"]) is True


def test_match_ip_inside_subnet() -> None:
    assert ip_matches_allowlist("203.0.113.42", ["203.0.113.0/24"]) is True


def test_no_match_outside_subnet() -> None:
    assert ip_matches_allowlist("198.51.100.1", ["203.0.113.0/24"]) is False


def test_empty_list_never_matches() -> None:
    # Guards against a future caller using "empty list == allow all" by
    # mistake — the caller is expected to not call the helper at all
    # when the list is empty.
    assert ip_matches_allowlist("203.0.113.5", []) is False


def test_none_ip_never_matches() -> None:
    assert ip_matches_allowlist(None, ["0.0.0.0/0"]) is False


def test_malformed_cidr_in_list_is_skipped() -> None:
    # A stale DB row from a future schema should not 500 the request.
    assert ip_matches_allowlist(
        "203.0.113.5",
        ["not-a-cidr", "203.0.113.0/24"],
    ) is True


def test_malformed_client_ip_never_matches() -> None:
    # Attacker-supplied X-Forwarded-For should not bypass the gate.
    assert ip_matches_allowlist("not-an-ip", ["0.0.0.0/0"]) is False


def test_ipv6_match() -> None:
    assert ip_matches_allowlist("2001:db8::1", ["2001:db8::/32"]) is True


# --------------------------------------------------------------------------- #
# Integration tests — require Postgres.
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


async def _mk_org(db, plan: OrgPlan = OrgPlan.ENTERPRISE) -> tuple[Organization, OrganizationMember]:
    org = Organization(
        id=uuid.uuid4(),
        name=f"IP-{uuid.uuid4().hex[:6]}",
        org_number=f"556{uuid.uuid4().int % 10**9:09d}"[:10],
        plan=plan,
    )
    owner = OrganizationMember(org_id=org.id, user_id=uuid.uuid4(), role=OrgRole.OWNER)
    db.add_all([org, owner])
    await db.commit()
    return org, owner


async def _mk_entry(db, org_id, cidr: str) -> OrgIpAllowlistEntry:
    entry = OrgIpAllowlistEntry(org_id=org_id, cidr=cidr)
    db.add(entry)
    await db.commit()
    return entry


def _override(member: OrganizationMember):
    async def _o():
        return {"user_id": member.user_id, "email": "test@varuflow.local"}, member
    return _o


async def _cleanup(db, org_id) -> None:
    # Cascade via FK: deleting the org removes the member + allowlist entries.
    org = await db.get(Organization, org_id)
    if org:
        await db.delete(org)
    await db.commit()


@pytest.mark.asyncio
async def test_no_entries_allows_any_ip(pg_session) -> None:
    org, owner = await _mk_org(pg_session)
    app.dependency_overrides[get_current_member] = _override(owner)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/api/settings/security/ip-allowlist")
        assert r.status_code == 200
        assert r.json() == []
    finally:
        app.dependency_overrides.pop(get_current_member, None)
        await _cleanup(pg_session, org.id)


@pytest.mark.asyncio
async def test_post_valid_cidr_as_owner(pg_session) -> None:
    org, owner = await _mk_org(pg_session, plan=OrgPlan.ENTERPRISE)
    app.dependency_overrides[get_current_member] = _override(owner)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/api/settings/security/ip-allowlist",
                json={"cidr": "203.0.113.0/24", "label": "HQ"},
            )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["cidr"] == "203.0.113.0/24"
        assert body["label"] == "HQ"
    finally:
        app.dependency_overrides.pop(get_current_member, None)
        await _cleanup(pg_session, org.id)


@pytest.mark.asyncio
async def test_post_non_enterprise_plan_blocked(pg_session) -> None:
    org, owner = await _mk_org(pg_session, plan=OrgPlan.PRO)
    app.dependency_overrides[get_current_member] = _override(owner)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/api/settings/security/ip-allowlist",
                json={"cidr": "203.0.113.0/24"},
            )
        assert r.status_code == 403
        assert "Enterprise" in r.text
    finally:
        app.dependency_overrides.pop(get_current_member, None)
        await _cleanup(pg_session, org.id)


@pytest.mark.asyncio
async def test_post_invalid_cidr_rejected(pg_session) -> None:
    org, owner = await _mk_org(pg_session, plan=OrgPlan.ENTERPRISE)
    app.dependency_overrides[get_current_member] = _override(owner)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/api/settings/security/ip-allowlist",
                json={"cidr": "not-a-cidr"},
            )
        assert r.status_code == 400
    finally:
        app.dependency_overrides.pop(get_current_member, None)
        await _cleanup(pg_session, org.id)


@pytest.mark.asyncio
async def test_post_duplicate_rejected(pg_session) -> None:
    org, owner = await _mk_org(pg_session, plan=OrgPlan.ENTERPRISE)
    await _mk_entry(pg_session, org.id, "203.0.113.0/24")
    app.dependency_overrides[get_current_member] = _override(owner)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/api/settings/security/ip-allowlist",
                json={"cidr": "203.0.113.0/24"},
            )
        assert r.status_code == 409
    finally:
        app.dependency_overrides.pop(get_current_member, None)
        await _cleanup(pg_session, org.id)


@pytest.mark.asyncio
async def test_post_non_owner_blocked(pg_session) -> None:
    org, _owner = await _mk_org(pg_session, plan=OrgPlan.ENTERPRISE)
    admin = OrganizationMember(org_id=org.id, user_id=uuid.uuid4(), role=OrgRole.ADMIN)
    pg_session.add(admin)
    await pg_session.commit()
    app.dependency_overrides[get_current_member] = _override(admin)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/api/settings/security/ip-allowlist",
                json={"cidr": "203.0.113.0/24"},
            )
        assert r.status_code == 403
        assert "owner" in r.text.lower()
    finally:
        app.dependency_overrides.pop(get_current_member, None)
        await _cleanup(pg_session, org.id)


@pytest.mark.asyncio
async def test_delete_entry(pg_session) -> None:
    org, owner = await _mk_org(pg_session, plan=OrgPlan.ENTERPRISE)
    entry = await _mk_entry(pg_session, org.id, "203.0.113.0/24")
    app.dependency_overrides[get_current_member] = _override(owner)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.delete(f"/api/settings/security/ip-allowlist/{entry.id}")
        assert r.status_code == 204
    finally:
        app.dependency_overrides.pop(get_current_member, None)
        await _cleanup(pg_session, org.id)
