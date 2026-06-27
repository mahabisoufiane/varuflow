"""Onboarding checklist integration tests (v26).

Covers:
  * GET /api/onboarding returns 0% for a fresh org.
  * POST /api/onboarding/complete-step rejects unknown steps.
  * Completing all six steps yields completion_pct == 100.
  * Re-submitting the same step is a no-op (no duplicate rows,
    completion_pct does not exceed 100).

Requires a live PostgreSQL — skipped automatically via the shared
``db_session`` fixture when Postgres is unreachable.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select, func

from app.models.onboarding import OnboardingProgress
from app.routers.onboarding import ONBOARDING_STEPS



async def test_initial_status_is_zero(two_orgs, client_factory):
    member = two_orgs["a"]["member"]
    async with client_factory(member) as client:
        r = await client.get("/api/onboarding")
        assert r.status_code == 200
        body = r.json()
        assert body["completed_steps"] == []
        assert body["completion_pct"] == 0
        assert body["next_step"] == ONBOARDING_STEPS[0]


async def test_unknown_step_rejected(two_orgs, client_factory):
    member = two_orgs["a"]["member"]
    async with client_factory(member) as client:
        r = await client.post(
            "/api/onboarding/complete-step",
            json={"step": "NOT_A_REAL_STEP"},
        )
        assert r.status_code == 400


async def test_complete_all_steps_hits_100(db_session, two_orgs, client_factory):
    member = two_orgs["a"]["member"]
    async with client_factory(member) as client:
        last_body: dict | None = None
        for step in ONBOARDING_STEPS:
            r = await client.post(
                "/api/onboarding/complete-step",
                json={"step": step},
            )
            assert r.status_code == 200
            last_body = r.json()

        assert last_body is not None
        assert last_body["completion_pct"] == 100
        assert set(last_body["completed_steps"]) == set(ONBOARDING_STEPS)
        assert last_body["next_step"] is None

    # Exactly 6 rows — no duplicates.
    count = (
        await db_session.execute(
            select(func.count()).select_from(OnboardingProgress)
            .where(OnboardingProgress.org_id == member.org_id)
        )
    ).scalar()
    assert count == len(ONBOARDING_STEPS)


async def test_duplicate_step_is_noop(db_session, two_orgs, client_factory):
    member = two_orgs["a"]["member"]
    async with client_factory(member) as client:
        r1 = await client.post(
            "/api/onboarding/complete-step",
            json={"step": "ADD_FIRST_PRODUCT"},
        )
        r2 = await client.post(
            "/api/onboarding/complete-step",
            json={"step": "ADD_FIRST_PRODUCT"},
        )
        assert r1.status_code == 200
        assert r2.status_code == 200
        # Completion percentage does not double-count.
        assert r2.json()["completion_pct"] == r1.json()["completion_pct"]

    count = (
        await db_session.execute(
            select(func.count()).select_from(OnboardingProgress)
            .where(
                OnboardingProgress.org_id == member.org_id,
                OnboardingProgress.step == "ADD_FIRST_PRODUCT",
            )
        )
    ).scalar()
    assert count == 1


async def test_isolation_between_orgs(two_orgs, client_factory):
    """Org A's progress must not leak into org B's status."""
    member_a = two_orgs["a"]["member"]
    member_b = two_orgs["b"]["member"]

    async with client_factory(member_a) as client:
        await client.post(
            "/api/onboarding/complete-step",
            json={"step": "ADD_FIRST_PRODUCT"},
        )

    async with client_factory(member_b) as client:
        r = await client.get("/api/onboarding")
        assert r.json()["completion_pct"] == 0
        assert r.json()["completed_steps"] == []
