"""Subscription pause service (Item 50).

Pure, stdlib-only helpers: duration validation, plan-eligibility
check, reminder scheduling math, and Stripe argument builders. No
DB, no FastAPI, no Pydantic — the router composes these with
SQLAlchemy queries and ``stripe.Subscription.modify``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


# ═══════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════

# Maximum pause duration — 90 days matches the Stripe + industry norm.
# Beyond this we'd need to rotate auth tokens, revisit data retention,
# and trigger GDPR delete timelines, so the hard ceiling protects us.
MAX_PAUSE_DAYS = 90

# Minimum pause — a 0-day pause is a no-op; 1 day prevents the UI
# from accidentally shipping a resume email at the same moment the
# pause lands.
MIN_PAUSE_DAYS = 1

# How many days before auto-resume we email the operator. 7 gives
# enough runway for a "pause another 30" decision without forcing the
# customer to check billing daily.
REMINDER_DAYS_BEFORE = 7

# Plans eligible to pause. FREE tier has nothing to pause — Stripe
# won't accept pause_collection on a non-subscription account.
PLANS_ELIGIBLE_TO_PAUSE = ("PRO", "ENTERPRISE")


# ═══════════════════════════════════════════════════════════════════
# Validation (pure)
# ═══════════════════════════════════════════════════════════════════


def validate_pause_duration(days: int) -> int:
    """Coerce to int and enforce the 1..90 bound. Raises ``ValueError``
    on out-of-range input so the router can convert to a 422."""
    try:
        d = int(days)
    except (TypeError, ValueError) as exc:
        raise ValueError("pause_days_must_be_integer") from exc
    if d < MIN_PAUSE_DAYS:
        raise ValueError("pause_days_below_minimum")
    if d > MAX_PAUSE_DAYS:
        raise ValueError("pause_days_exceeds_maximum")
    return d


def can_pause_plan(plan: str) -> bool:
    """True when the given plan is eligible to pause.

    Accepts both the raw enum value (``"PRO"``) and lowercase input
    so callers don't have to remember which the DB returns."""
    if not plan:
        return False
    return str(plan).upper() in PLANS_ELIGIBLE_TO_PAUSE


# ═══════════════════════════════════════════════════════════════════
# Schedule math (pure, timezone-safe)
# ═══════════════════════════════════════════════════════════════════


def compute_pause_end(days: int, now: datetime | None = None) -> datetime:
    """Canonical pause-end = ``now + days`` (UTC). Validates the
    duration before computing."""
    d = validate_pause_duration(days)
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now + timedelta(days=d)


def is_reminder_due(
    pause_ends_at: datetime,
    reminder_sent_at: datetime | None,
    now: datetime | None = None,
) -> bool:
    """True when a reminder email should be sent right now.

    A reminder is due when:
      1. It hasn't already been sent for this pause window, AND
      2. The auto-resume moment is within :data:`REMINDER_DAYS_BEFORE`
         days from now, AND
      3. The pause hasn't already elapsed."""
    if reminder_sent_at is not None:
        return False
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if pause_ends_at.tzinfo is None:
        pause_ends_at = pause_ends_at.replace(tzinfo=timezone.utc)
    if pause_ends_at <= now:
        # Already elapsed — auto-resume sweep handles this.
        return False
    remaining = pause_ends_at - now
    return remaining <= timedelta(days=REMINDER_DAYS_BEFORE)


def should_auto_resume(
    pause_ends_at: datetime, now: datetime | None = None
) -> bool:
    """True when ``now`` is at or past ``pause_ends_at``."""
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if pause_ends_at.tzinfo is None:
        pause_ends_at = pause_ends_at.replace(tzinfo=timezone.utc)
    return now >= pause_ends_at


# ═══════════════════════════════════════════════════════════════════
# Stripe argument builders (pure)
# ═══════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class PauseCommand:
    """Arguments for ``stripe.Subscription.modify``. Named so tests
    can assert exact shape without touching the Stripe SDK."""
    subscription_id: str
    pause_collection: dict


def build_pause_command(subscription_id: str) -> PauseCommand:
    """Build the Stripe pause request. We use ``behavior='void'`` so
    no invoices are generated during the pause — the customer pays
    for zero days of service. ``mark_uncollectible`` would still
    create invoices that we'd have to reconcile later."""
    if not subscription_id:
        raise ValueError("subscription_id_required")
    return PauseCommand(
        subscription_id=subscription_id,
        pause_collection={"behavior": "void"},
    )


def build_resume_command(subscription_id: str) -> PauseCommand:
    """Build the Stripe resume request. Stripe interprets an empty
    ``pause_collection`` object as "lift the pause and resume
    collection immediately"."""
    if not subscription_id:
        raise ValueError("subscription_id_required")
    return PauseCommand(
        subscription_id=subscription_id,
        pause_collection={},
    )
