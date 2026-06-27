"""M-3: GDPR endpoint tests — export and erasure.

Covers:
  GET    /api/gdpr/export        — Art. 15 / Art. 20 data portability
  DELETE /api/gdpr/organization  — Art. 17 erasure (logical anonymisation)

All tests require PostgreSQL (run `docker compose up db` or set DATABASE_URL).
"""
from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import delete as _sql_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.invoicing.models import Customer
from app.features.auth.organization import OrgPlan, Organization, OrganizationMember, OrgRole


# ─────────────────────────────────────────────────────────────────────────────
# Fixture: one org with owner + admin member
# ─────────────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def gdpr_org(db_session: AsyncSession):
    """Single ENTERPRISE org with an OWNER and an ADMIN member.

    ENTERPRISE so require_module("settings") passes. "settings" is available
    on all plans, but ENTERPRISE also gives us access to all other modules
    without needing per-test plan overrides.
    """
    org_id = uuid.uuid4()
    org = Organization(
        id=org_id,
        name="GDPR Test Org",
        org_number="556999-0001",
        plan=OrgPlan.ENTERPRISE,
    )
    owner_user_id = uuid.uuid4()
    admin_user_id = uuid.uuid4()

    owner = OrganizationMember(org_id=org_id, user_id=owner_user_id, role=OrgRole.OWNER)
    admin = OrganizationMember(org_id=org_id, user_id=admin_user_id, role=OrgRole.ADMIN)

    db_session.add_all([org, owner, admin])
    await db_session.commit()

    yield {"org": org, "owner": owner, "admin": admin}

    # Teardown — SQL DELETE cascades to members and any child rows seeded in tests.
    await db_session.execute(_sql_delete(Organization).where(Organization.id == org_id))
    await db_session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────


async def _seed_customer(db: AsyncSession, org_id: uuid.UUID, name: str) -> Customer:
    c = Customer(org_id=org_id, company_name=name, email="test@example.com")
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/gdpr/export — owner
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_export_owner_succeeds(gdpr_org, client_factory):
    """OWNER may call GET /api/gdpr/export and receives a JSON download."""
    async with client_factory(gdpr_org["owner"]) as client:
        r = await client.get("/api/gdpr/export")

    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
    assert r.headers["content-type"].startswith("application/json")
    assert "attachment" in r.headers.get("content-disposition", "")

    payload: dict[str, Any] = r.json()
    assert "generated_at" in payload
    assert "organization" in payload
    assert "customers" in payload
    assert "invoices" in payload
    assert "members" in payload
    assert isinstance(payload["customers"], list)
    assert isinstance(payload["invoices"], list)
    assert isinstance(payload["members"], list)


@pytest.mark.asyncio
async def test_export_non_owner_forbidden(gdpr_org, client_factory):
    """ADMIN (non-owner) is refused with 403.

    GDPR export is restricted to OWNER — the authoritative data controller.
    An ADMIN could abuse the export to exfiltrate the org's full PII payload.
    """
    async with client_factory(gdpr_org["admin"]) as client:
        r = await client.get("/api/gdpr/export")

    assert r.status_code == 403, (
        f"ADMIN should be blocked from GDPR export (got {r.status_code})"
    )


@pytest.mark.asyncio
async def test_export_strips_credential_columns(gdpr_org, client_factory):
    """Fortnox tokens and Stripe customer ID must not appear in the export.

    These are third-party API credentials, not personal data under GDPR Art. 15.
    Leaking them in an emailed/downloaded JSON hands an attacker live sessions
    against Fortnox or Stripe.
    """
    async with client_factory(gdpr_org["owner"]) as client:
        r = await client.get("/api/gdpr/export")

    assert r.status_code == 200
    raw = r.text
    assert "fortnox_access_token" not in raw, "fortnox_access_token must be stripped"
    assert "fortnox_refresh_token" not in raw, "fortnox_refresh_token must be stripped"
    assert "stripe_customer_id" not in raw, "stripe_customer_id must be stripped"


@pytest.mark.asyncio
async def test_export_includes_seeded_customer(db_session, gdpr_org, client_factory):
    """Customer rows seeded for this org must appear in the export payload."""
    org_id = gdpr_org["org"].id
    await _seed_customer(db_session, org_id, "Seeded Customer AB")

    async with client_factory(gdpr_org["owner"]) as client:
        r = await client.get("/api/gdpr/export")

    assert r.status_code == 200
    payload = r.json()
    customer_names = [c["company_name"] for c in payload["customers"]]
    assert "Seeded Customer AB" in customer_names, (
        f"Seeded customer not in export. Got: {customer_names}"
    )


@pytest.mark.asyncio
async def test_export_does_not_include_other_org_data(db_session, gdpr_org, client_factory):
    """Export must only include rows scoped to the caller's org."""
    # Create a second org and seed a customer under it
    other_org_id = uuid.uuid4()
    other_org = Organization(
        id=other_org_id,
        name="Other Org",
        org_number="556999-9999",
        plan=OrgPlan.FREE,
    )
    db_session.add(other_org)
    await db_session.commit()
    await _seed_customer(db_session, other_org_id, "Other Org Customer")

    try:
        async with client_factory(gdpr_org["owner"]) as client:
            r = await client.get("/api/gdpr/export")

        assert r.status_code == 200
        payload = r.json()
        customer_names = [c["company_name"] for c in payload["customers"]]
        assert "Other Org Customer" not in customer_names, (
            "LEAK: another org's customer appeared in GDPR export"
        )
    finally:
        await db_session.execute(
            _sql_delete(Organization).where(Organization.id == other_org_id)
        )
        await db_session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /api/gdpr/organization — erasure
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_requires_confirmation_header(gdpr_org, client_factory):
    """DELETE without X-Confirm-Delete header returns 400."""
    async with client_factory(gdpr_org["owner"]) as client:
        r = await client.delete("/api/gdpr/organization")

    assert r.status_code == 400, (
        f"Missing confirmation header should be 400 (got {r.status_code})"
    )


@pytest.mark.asyncio
async def test_delete_wrong_confirmation_value_rejected(gdpr_org, client_factory):
    """DELETE with wrong X-Confirm-Delete value returns 400."""
    async with client_factory(gdpr_org["owner"]) as client:
        r = await client.delete(
            "/api/gdpr/organization",
            headers={"X-Confirm-Delete": "yes"},
        )

    assert r.status_code == 400, (
        f"Wrong confirmation value should be 400 (got {r.status_code})"
    )


@pytest.mark.asyncio
async def test_delete_non_owner_forbidden(gdpr_org, client_factory):
    """ADMIN role is blocked from the erasure endpoint."""
    async with client_factory(gdpr_org["admin"]) as client:
        r = await client.delete(
            "/api/gdpr/organization",
            headers={"X-Confirm-Delete": "DELETE"},
        )

    assert r.status_code == 403, (
        f"ADMIN should be blocked from org erasure (got {r.status_code})"
    )


@pytest.mark.asyncio
async def test_delete_anonymizes_org_pii(db_session, gdpr_org, client_factory):
    """Confirmed DELETE anonymises the org and removes members.

    The org row is retained (with placeholder values) for foreign-key
    integrity with invoices/payments, per Swedish bokföringslagen 7 kap. 2 §.
    Members are hard-deleted so the humans lose access immediately.

    Note: this test is last because it mutates the shared org fixture.
    The fixture teardown handles cleanup via SQL DELETE CASCADE.
    """
    org_id = gdpr_org["org"].id
    # Seed a customer to verify anonymisation cascades to customer PII
    await _seed_customer(db_session, org_id, "PII Customer AB")

    async with client_factory(gdpr_org["owner"]) as client:
        r = await client.delete(
            "/api/gdpr/organization",
            headers={"X-Confirm-Delete": "DELETE"},
        )

    assert r.status_code == 204, (
        f"Confirmed erasure should return 204 (got {r.status_code}: {r.text[:200]})"
    )

    # Re-read the org — must still exist (retained for BFL) but anonymised
    await db_session.expire_all()
    org = await db_session.get(Organization, org_id)
    assert org is not None, "Org row must be retained after GDPR erasure (BFL)"
    assert org.is_active is False, "Org must be deactivated after erasure"
    assert "Deleted organization" in (org.name or ""), (
        f"Org name was not anonymised: {org.name!r}"
    )

    # Members must be removed — no more access
    remaining_members = (
        await db_session.scalars(
            select(OrganizationMember).where(OrganizationMember.org_id == org_id)
        )
    ).all()
    assert len(remaining_members) == 0, (
        f"All members should be removed after erasure ({len(remaining_members)} remain)"
    )

    # Customers must be anonymised
    customers = (
        await db_session.scalars(
            select(Customer).where(Customer.org_id == org_id)
        )
    ).all()
    for c in customers:
        assert c.email is None, f"Customer email not cleared: {c.email!r}"
        assert "Deleted customer" in (c.company_name or ""), (
            f"Customer name not anonymised: {c.company_name!r}"
        )
