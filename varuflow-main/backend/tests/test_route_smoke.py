"""Route smoke test — walk every parameterless GET /api route, fail on any 5xx.

Motivation (2026-07-06 audit): a whole class of shipped-but-never-executed
endpoints was silently broken — routers nested under a doubled prefix, raw SQL
written against columns that don't exist, dependency objects bound to the
wrong parameter. All of them 500'd on first real call, and all of them would
have been caught by simply GET-ing every registered route once.

This test does exactly that with an ENTERPRISE-plan owner (so plan/module
gates pass and the handler bodies actually execute). 4xx responses are fine —
missing resources / plan gates / validation are legitimate. 5xx never is.
"""
from __future__ import annotations

import uuid

import pytest_asyncio
from fastapi.routing import APIRoute

from app.main import app
from app.features.auth.organization import (
    Organization,
    OrganizationMember,
    OrgPlan,
    OrgRole,
)


@pytest_asyncio.fixture
async def smoke_org(db_session):
    """ENTERPRISE org + OWNER member so gates pass and handlers run."""
    org = Organization(
        id=uuid.uuid4(),
        name="Smoke Test AB",
        org_number="556000-9999",
        plan=OrgPlan.ENTERPRISE,
    )
    user_id = uuid.uuid4()
    member = OrganizationMember(org_id=org.id, user_id=user_id, role=OrgRole.OWNER)
    db_session.add_all([org, member])
    await db_session.commit()
    yield member
    # Delete member first — the ORM relationship nulls org_id on org delete,
    # which violates the NOT NULL constraint.
    await db_session.delete(member)
    await db_session.delete(org)
    await db_session.commit()


def _parameterless_get_routes() -> list[str]:
    paths = set()
    for r in app.routes:
        if (
            isinstance(r, APIRoute)
            and "GET" in r.methods
            and "{" not in r.path
            and r.path.startswith("/api")
        ):
            paths.add(r.path)
    return sorted(paths)


async def test_every_parameterless_get_returns_no_5xx(smoke_org, client_factory):
    failures: list[str] = []
    routes = _parameterless_get_routes()
    assert len(routes) > 100, f"route collection looks broken ({len(routes)} routes)"
    async with client_factory(smoke_org) as client:
        for path in routes:
            resp = await client.get(path)
            # 503 is this codebase's designed "integration not configured"
            # response (Fortnox, Stripe Terminal, BankID, …) — legitimate in
            # environments without those credentials. Everything else 5xx is
            # a defect.
            if resp.status_code >= 500 and resp.status_code != 503:
                failures.append(f"  {resp.status_code} {path}")
    assert not failures, (
        f"{len(failures)}/{len(routes)} GET routes returned 5xx:\n"
        + "\n".join(failures)
    )
