"""Pure trial helpers + DB-bound mutations for the 14-day PRO trial system."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.organization import OrgPlan, Organization

logger = logging.getLogger(__name__)

TRIAL_DURATION_DAYS = 14
EXTENSION_DAYS = 7
MAX_EXTENSIONS = 1
GRACE_PERIOD_DAYS = 1
REMINDER_DAY = 13  # send at day 13 (1 day before expiry)


# ── Pure helpers (no DB) ──────────────────────────────────────────────────────


def is_trial_active(org: Organization, now: datetime | None = None) -> bool:
    """Return True if the org currently has a live trial."""
    now = now or datetime.now(timezone.utc)
    if org.trial_started_at is None or org.trial_ends_at is None:
        return False
    if org.trial_converted_at is not None:
        return False
    return now < org.trial_ends_at


def days_remaining(org: Organization, now: datetime | None = None) -> int:
    """Days left in the trial (0 if inactive or expired)."""
    now = now or datetime.now(timezone.utc)
    if not is_trial_active(org, now):
        return 0
    delta = org.trial_ends_at - now
    return max(0, delta.days)


def can_extend(org: Organization) -> bool:
    """True if the org is eligible for a one-time 7-day extension."""
    return (
        org.trial_started_at is not None
        and org.trial_converted_at is None
        and org.trial_extended_count < MAX_EXTENSIONS
    )


def _assert_eligible(org: Organization) -> None:
    """Raise ValueError if the org cannot start a trial."""
    if org.plan != OrgPlan.FREE:
        raise ValueError("trial_already_paid")
    if org.trial_started_at is not None and org.trial_converted_at is None:
        raise ValueError("trial_already_active")
    if org.trial_started_at is not None and org.trial_converted_at is None:
        raise ValueError("trial_already_used")


def start_trial(
    org: Organization,
    plan: str,
    source: str,
    now: datetime | None = None,
) -> Organization:
    """
    Validate eligibility and set trial fields on *org* (does NOT flush/commit).
    The caller owns the DB session and must commit.
    """
    now = now or datetime.now(timezone.utc)

    if org.plan != OrgPlan.FREE:
        raise ValueError("trial_already_paid")
    if org.trial_started_at is not None and org.trial_converted_at is None:
        raise ValueError("trial_already_active")
    if (
        org.trial_started_at is not None
        and org.trial_converted_at is not None
    ):
        raise ValueError("trial_already_used")

    org.trial_plan = plan
    org.trial_started_at = now
    org.trial_ends_at = now + timedelta(days=TRIAL_DURATION_DAYS)
    org.trial_source = source
    return org


# ── DB-bound mutations ────────────────────────────────────────────────────────


async def extend_trial(
    org: Organization,
    db: AsyncSession,
    now: datetime | None = None,
) -> Organization:
    """
    Add EXTENSION_DAYS to the trial end date.
    Raises ValueError on ineligibility.
    Flushes but does NOT commit — caller commits.
    """
    now = now or datetime.now(timezone.utc)

    if not can_extend(org):
        raise ValueError("trial_extension_not_allowed")

    # Allow extension even if already expired (within reason)
    base = max(org.trial_ends_at, now)
    org.trial_ends_at = base + timedelta(days=EXTENSION_DAYS)
    org.trial_extended_count += 1
    await db.flush()
    return org


async def convert_trial(
    org: Organization,
    db: AsyncSession,
    now: datetime | None = None,
) -> Organization:
    """
    Mark the trial as converted to paid. Sets trial_converted_at.
    Flushes but does NOT commit — caller commits.
    """
    now = now or datetime.now(timezone.utc)
    org.trial_converted_at = now
    await db.flush()
    return org


async def expire_trial(
    org: Organization,
    db: AsyncSession,
) -> Organization:
    """
    Downgrade back to FREE after trial expires.
    Caller must call convert_trial first OR handle plan separately.
    Flushes but does NOT commit — caller commits.
    """
    org.plan = OrgPlan.FREE
    await db.flush()
    return org


async def fetch_orgs_for_sweep(db: AsyncSession, now: datetime) -> list[Organization]:
    """Return orgs whose trial ends within a sweep window (past 2 days → future 2 days)."""
    window_start = now - timedelta(days=GRACE_PERIOD_DAYS + 1)
    window_end = now + timedelta(days=REMINDER_DAY - TRIAL_DURATION_DAYS + 1)
    result = await db.execute(
        select(Organization).where(
            Organization.trial_ends_at.isnot(None),
            Organization.trial_converted_at.is_(None),
            Organization.trial_ends_at >= window_start,
            Organization.trial_ends_at <= window_end + timedelta(days=2),
        )
    )
    return list(result.scalars().all())
