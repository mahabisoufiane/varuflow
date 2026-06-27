"""Tests for /api/audit — owner-only audit log read endpoint."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLogEntry
from app.models.organization import OrgRole, OrganizationMember




async def test_owner_can_list_own_org_entries(two_orgs, client_factory, db_session: AsyncSession):
    org_a = two_orgs["a"]["org"]
    org_b = two_orgs["b"]["org"]

    db_session.add_all([
        AuditLogEntry(org_id=org_a.id, action="billing.plan_upgraded", target_type="organization", target_id=str(org_a.id)),
        AuditLogEntry(org_id=org_a.id, action="team.role_changed",     target_type="organization_member", target_id=str(uuid.uuid4())),
        AuditLogEntry(org_id=org_b.id, action="gdpr.org_anonymise",    target_type="organization", target_id=str(org_b.id)),
    ])
    await db_session.commit()

    async with client_factory(two_orgs["a"]["member"]) as client:
        res = await client.get("/api/audit")
        assert res.status_code == 200
        rows = res.json()
        assert len(rows) == 2
        actions = {r["action"] for r in rows}
        assert actions == {"billing.plan_upgraded", "team.role_changed"}


async def test_non_owner_is_forbidden(two_orgs, client_factory):
    member = two_orgs["a"]["member"]
    member.role = OrgRole.MEMBER
    async with client_factory(member) as client:
        res = await client.get("/api/audit")
        assert res.status_code == 403


async def test_action_filter(two_orgs, client_factory, db_session: AsyncSession):
    org_a = two_orgs["a"]["org"]
    db_session.add_all([
        AuditLogEntry(org_id=org_a.id, action="billing.plan_upgraded", target_type="organization", target_id=str(org_a.id)),
        AuditLogEntry(org_id=org_a.id, action="team.role_changed",     target_type="organization_member", target_id=str(uuid.uuid4())),
    ])
    await db_session.commit()

    async with client_factory(two_orgs["a"]["member"]) as client:
        res = await client.get("/api/audit?action=billing.plan_upgraded")
        assert res.status_code == 200
        rows = res.json()
        assert len(rows) == 1
        assert rows[0]["action"] == "billing.plan_upgraded"


async def test_pagination_caps(two_orgs, client_factory):
    async with client_factory(two_orgs["a"]["member"]) as client:
        # limit > 200 must be rejected
        res = await client.get("/api/audit?limit=500")
        assert res.status_code == 422
        # negative offset must be rejected
        res = await client.get("/api/audit?offset=-1")
        assert res.status_code == 422
