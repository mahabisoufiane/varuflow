"""H-5: Scheduler background-job tenant isolation.

All scheduler jobs run cross-org sweeps intentionally (one DB session processes
all tenants). The isolation invariant is: data from org A is never *delivered*
to org B. This module verifies the sweeps modify only the records that match
the job's criteria and respects per-org ownership throughout.

Key pattern tested: _quote_expiry_sweep marks quotes whose valid_until < today
and status in ('sent','viewed') as expired. An expired quote from org_a must
not affect org_b's valid quote.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def two_sched_orgs(db_session: AsyncSession):
    """Two orgs, each with one customer — minimal seed for scheduler tests."""
    from sqlalchemy import delete as _sql_delete

    from app.features.invoicing.models import Customer
    from app.features.auth.organization import Organization, OrganizationMember, OrgPlan, OrgRole

    org_a = Organization(
        id=uuid.uuid4(),
        name="Sched Alpha AB",
        org_number="556300-0011",
        plan=OrgPlan.ENTERPRISE,
    )
    org_b = Organization(
        id=uuid.uuid4(),
        name="Sched Bravo AB",
        org_number="556300-0012",
        plan=OrgPlan.ENTERPRISE,
    )
    u_a, u_b = uuid.uuid4(), uuid.uuid4()
    m_a = OrganizationMember(org_id=org_a.id, user_id=u_a, role=OrgRole.OWNER)
    m_b = OrganizationMember(org_id=org_b.id, user_id=u_b, role=OrgRole.OWNER)
    cust_a = Customer(org_id=org_a.id, company_name="Sched Cust A")
    cust_b = Customer(org_id=org_b.id, company_name="Sched Cust B")
    db_session.add_all([org_a, org_b, m_a, m_b, cust_a, cust_b])
    await db_session.commit()

    yield {
        "a": {"org": org_a, "customer": cust_a},
        "b": {"org": org_b, "customer": cust_b},
    }

    # ON DELETE CASCADE handles child rows; SQL DELETE bypasses ORM cascade issue
    await db_session.execute(
        _sql_delete(Organization).where(Organization.id.in_([org_a.id, org_b.id]))
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_quote_expiry_sweep_isolation(two_sched_orgs, db_session: AsyncSession):
    """_quote_expiry_sweep must expire org_a's overdue quote without touching org_b's valid one.

    Seeds two quotes committed to the DB, calls the real sweep (which opens its
    own session), then re-reads both rows to confirm only the expired one changed.
    """
    from sqlalchemy import select

    from app.features.invoicing.model_quotes import Quote
    from app.services.scheduler import _quote_expiry_sweep

    org_a_id = two_sched_orgs["a"]["org"].id
    org_b_id = two_sched_orgs["b"]["org"].id
    cust_a_id = two_sched_orgs["a"]["customer"].id
    cust_b_id = two_sched_orgs["b"]["customer"].id

    yesterday = date.today() - timedelta(days=1)
    next_week = date.today() + timedelta(days=7)

    q_a = Quote(
        org_id=org_a_id,
        customer_id=cust_a_id,
        title="Expired Quote Alpha",
        valid_until=yesterday,
        status="sent",
    )
    q_b = Quote(
        org_id=org_b_id,
        customer_id=cust_b_id,
        title="Valid Quote Bravo",
        valid_until=next_week,
        status="sent",
    )
    db_session.add_all([q_a, q_b])
    await db_session.commit()
    q_a_id, q_b_id = q_a.id, q_b.id

    # Sweep uses its own session factory; data must be committed first (done above)
    await _quote_expiry_sweep()

    # Re-read both rows in a fresh query to see the sweep's changes
    row_a = (
        await db_session.execute(select(Quote).where(Quote.id == q_a_id))
    ).scalar_one_or_none()
    row_b = (
        await db_session.execute(select(Quote).where(Quote.id == q_b_id))
    ).scalar_one_or_none()

    assert row_a is not None, "org_a quote disappeared unexpectedly"
    assert row_b is not None, "org_b quote disappeared unexpectedly"
    assert row_a.status == "expired", (
        f"SCHEDULER ISOLATION BUG: org_a's overdue quote was not expired "
        f"(status={row_a.status})"
    )
    assert row_b.status == "sent", (
        f"SCHEDULER ISOLATION BUG: org_b's valid quote was wrongly changed "
        f"(status={row_b.status})"
    )


@pytest.mark.asyncio
async def test_quote_expiry_does_not_expire_draft(two_sched_orgs, db_session: AsyncSession):
    """Quotes in 'draft' status must not be expired even if past valid_until.

    The sweep only targets sent/viewed quotes — draft quotes are not visible
    to clients and should never be marked expired by the background job.
    """
    from sqlalchemy import select

    from app.features.invoicing.model_quotes import Quote
    from app.services.scheduler import _quote_expiry_sweep

    org_a_id = two_sched_orgs["a"]["org"].id
    cust_a_id = two_sched_orgs["a"]["customer"].id
    yesterday = date.today() - timedelta(days=1)

    q_draft = Quote(
        org_id=org_a_id,
        customer_id=cust_a_id,
        title="Draft Old Quote",
        valid_until=yesterday,
        status="draft",
    )
    db_session.add(q_draft)
    await db_session.commit()
    q_id = q_draft.id

    await _quote_expiry_sweep()

    row = (
        await db_session.execute(select(Quote).where(Quote.id == q_id))
    ).scalar_one_or_none()
    assert row is not None
    assert row.status == "draft", (
        f"Sweep must not expire draft quotes (status={row.status})"
    )


def test_scheduler_job_ids_registered():
    """All expected job IDs must be registered in the scheduler (smoke test)."""
    from app.services.scheduler import create_scheduler

    scheduler = create_scheduler()
    job_ids = {job.id for job in scheduler.get_jobs()}

    expected_ids = {
        "fortnox_sync",
        "low_stock_check",
        "weekly_digest",
        "token_cleanup",
        "dunning_sweep",
        "push_stockout",
        "push_overdue",
        "onboarding_reminder",
        "webhook_retry",
        "auto_reorder_check",
        "recurring_autosend",
        "nightly_summary_sweep",
        "segment_refresh",
        "campaign_dispatch",
        "quote_expiry_sweep",
        "trial_sweep",
    }
    missing = expected_ids - job_ids
    assert not missing, f"Scheduler jobs missing from registration: {missing}"
