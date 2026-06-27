"""Tests for portal replay prevention (Feature 10).

Covers:
  * magic-link single-use enforcement (replay → 400 + audit)
  * portal JWT session registration on verify
  * logout revokes the session (subsequent requests → 401)
  * tokens without a jti claim are rejected (forged / pre-v21 replay)
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import select

from app.config import settings
from app.main import app
from app.models.audit import AuditLogEntry
from app.models.invoicing import Customer, CustomerPortalToken
from app.models.organization import Organization
from app.models.portal_session import PortalSession




async def _postgres_ok(db):
    from sqlalchemy import text
    try:
        await db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest_asyncio.fixture
async def portal_fixture(db_session):
    if not await _postgres_ok(db_session):
        pytest.skip("PostgreSQL not reachable")

    org = Organization(
        id=uuid.uuid4(), name="Portal AB", org_number="556000-0010",
    )
    db_session.add(org)
    await db_session.commit()

    customer = Customer(
        org_id=org.id, company_name="Buyer AB", email="buyer@portal.test",
    )
    db_session.add(customer)
    await db_session.commit()
    await db_session.refresh(customer)

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    pt = CustomerPortalToken(
        customer_id=customer.id,
        org_id=org.id,
        token=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db_session.add(pt)
    await db_session.commit()

    yield {"org": org, "customer": customer, "raw_token": raw_token, "pt": pt}

    await db_session.delete(org)
    await db_session.commit()


async def test_magic_link_single_use(portal_fixture, db_session):
    """First verify succeeds; second verify is rejected and audited."""
    raw = portal_fixture["raw_token"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.get(f"/api/portal/auth/verify?token={raw}")
    assert r1.status_code == 200, r1.text
    jwt_token = r1.json()["portal_token"]
    assert jwt_token

    # Session row exists
    session_count = (await db_session.execute(
        select(PortalSession).where(PortalSession.customer_id == portal_fixture["customer"].id)
    )).scalars().all()
    assert len(session_count) == 1
    assert session_count[0].revoked_at is None

    # Replay of the SAME magic link → 400 + audit event
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r2 = await c.get(f"/api/portal/auth/verify?token={raw}")
    assert r2.status_code == 400

    replays = (await db_session.execute(
        select(AuditLogEntry).where(
            AuditLogEntry.action == "PORTAL_MAGIC_LINK_REPLAY",
            AuditLogEntry.org_id == portal_fixture["org"].id,
        )
    )).scalars().all()
    assert len(replays) == 1
    assert replays[0].target_id == str(portal_fixture["customer"].id)


async def test_portal_jwt_session_is_tracked(portal_fixture, db_session):
    """Issued portal JWT must carry a jti matching a portal_sessions row."""
    raw = portal_fixture["raw_token"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/portal/auth/verify?token={raw}")
    jwt_token = r.json()["portal_token"]

    payload = jwt.decode(
        jwt_token, settings.PORTAL_JWT_SECRET, algorithms=["HS256"],
        options={"verify_aud": False},
    )
    assert payload.get("jti"), "portal JWT must carry a jti claim"

    row = (await db_session.execute(
        select(PortalSession).where(PortalSession.jti == payload["jti"])
    )).scalar_one()
    assert row.customer_id == portal_fixture["customer"].id
    assert row.org_id == portal_fixture["org"].id
    assert row.revoked_at is None


async def test_logout_revokes_session(portal_fixture, db_session):
    """After POST /auth/logout the same JWT is rejected on protected routes."""
    raw = portal_fixture["raw_token"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/portal/auth/verify?token={raw}")
        jwt_token = r.json()["portal_token"]
        headers = {"Authorization": f"Bearer {jwt_token}"}

        # Sanity: invoices endpoint works before logout
        r_pre = await c.get("/api/portal/invoices", headers=headers)
        assert r_pre.status_code == 200

        r_out = await c.post("/api/portal/auth/logout", headers=headers)
        assert r_out.status_code == 200
        assert r_out.json()["status"] == "revoked"

        # After logout the JWT is dead
        r_post = await c.get("/api/portal/invoices", headers=headers)
    assert r_post.status_code == 401

    # DB confirms revocation stamp
    await db_session.commit()  # make sure we see the app's commit
    row = (await db_session.execute(
        select(PortalSession).where(
            PortalSession.customer_id == portal_fixture["customer"].id,
        )
    )).scalar_one()
    assert row.revoked_at is not None


async def test_portal_token_without_jti_rejected(portal_fixture):
    """A signed portal JWT that lacks a jti (forged / pre-v21) must 401."""
    forged = jwt.encode(
        {
            "sub": str(portal_fixture["customer"].id),
            "org_id": str(portal_fixture["org"].id),
            "type": "portal",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            # no jti
        },
        settings.PORTAL_JWT_SECRET,
        algorithm="HS256",
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            "/api/portal/invoices",
            headers={"Authorization": f"Bearer {forged}"},
        )
    assert r.status_code == 401


async def test_portal_token_with_unknown_jti_rejected(portal_fixture):
    """A token whose jti has no session row is rejected (revoked/forged)."""
    forged = jwt.encode(
        {
            "sub": str(portal_fixture["customer"].id),
            "org_id": str(portal_fixture["org"].id),
            "type": "portal",
            "jti": secrets.token_urlsafe(24),  # never registered
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.PORTAL_JWT_SECRET,
        algorithm="HS256",
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(
            "/api/portal/invoices",
            headers={"Authorization": f"Bearer {forged}"},
        )
    assert r.status_code == 401
