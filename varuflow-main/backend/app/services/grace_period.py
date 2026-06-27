"""Subscription grace-period service.

Pure helpers + async DB functions for managing payment-failure grace
windows. A grace period prevents immediate plan downgrade when a Stripe
invoice payment fails, giving the customer GRACE_PERIOD_DAYS to fix
their payment method.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.billing.grace_period import GracePeriodStatus, SubscriptionGracePeriod
from app.features.auth.organization import OrgPlan, Organization
from app.services.audit import log_action

log = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
GRACE_PERIOD_DAYS = 7
MAX_NOTIFICATIONS = 3


# ── Pure helpers ─────────────────────────────────────────────────────────────

def is_in_grace_period(grace: SubscriptionGracePeriod | None, now: datetime | None = None) -> bool:
    """Return True if the org has an active, non-expired grace period."""
    if grace is None or grace.status != GracePeriodStatus.ACTIVE:
        return False
    now = now or datetime.now(timezone.utc)
    return now < grace.expires_at


def days_remaining(grace: SubscriptionGracePeriod, now: datetime | None = None) -> int:
    """Return days remaining in the grace period (min 0)."""
    now = now or datetime.now(timezone.utc)
    delta = grace.expires_at - now
    return max(0, delta.days)


def should_notify(grace: SubscriptionGracePeriod, now: datetime | None = None) -> bool:
    """Return True if a reminder should be sent (max MAX_NOTIFICATIONS)."""
    if grace.status != GracePeriodStatus.ACTIVE:
        return False
    if grace.notification_sent_count >= MAX_NOTIFICATIONS:
        return False
    now = now or datetime.now(timezone.utc)
    remaining = days_remaining(grace, now)
    # Notify at 5, 3, 1 days remaining
    return remaining in (5, 3, 1)


# ── DB-bound functions ───────────────────────────────────────────────────────

async def get_active_grace_period(
    db: AsyncSession, org_id: uuid.UUID
) -> SubscriptionGracePeriod | None:
    """Return the active grace period for an org, if any."""
    result = await db.execute(
        select(SubscriptionGracePeriod)
        .where(
            SubscriptionGracePeriod.org_id == org_id,
            SubscriptionGracePeriod.status == GracePeriodStatus.ACTIVE,
        )
        .order_by(SubscriptionGracePeriod.triggered_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def start_grace_period(
    db: AsyncSession,
    org_id: uuid.UUID,
    failed_invoice_id: str | None = None,
    failed_amount_cents: int | None = None,
    failure_reason: str | None = None,
) -> SubscriptionGracePeriod:
    """Start a new grace period for an org.

    If one is already active, returns the existing one (idempotent).
    """
    existing = await get_active_grace_period(db, org_id)
    if existing:
        log.info("grace period already active for org %s", org_id)
        return existing

    now = datetime.now(timezone.utc)
    grace = SubscriptionGracePeriod(
        org_id=org_id,
        triggered_at=now,
        expires_at=now + timedelta(days=GRACE_PERIOD_DAYS),
        failed_invoice_id=failed_invoice_id,
        failed_amount_cents=failed_amount_cents,
        failure_reason=failure_reason,
        status=GracePeriodStatus.ACTIVE,
        notification_sent_count=1,  # initial notification counts
        last_notification_at=now,
    )
    db.add(grace)

    await log_action(
        db,
        action="billing.grace_period.started",
        org_id=org_id,
        target_type="subscription_grace_period",
        target_id=str(grace.id),
        extra={
            "failed_invoice_id": failed_invoice_id,
            "failed_amount_cents": failed_amount_cents,
            "grace_days": GRACE_PERIOD_DAYS,
        },
    )

    log.info("grace period started for org %s, expires %s", org_id, grace.expires_at)
    return grace


async def recover_grace_period(
    db: AsyncSession, org_id: uuid.UUID
) -> SubscriptionGracePeriod | None:
    """Mark the active grace period as recovered (payment succeeded)."""
    grace = await get_active_grace_period(db, org_id)
    if not grace:
        return None

    now = datetime.now(timezone.utc)
    grace.status = GracePeriodStatus.RECOVERED
    grace.recovered_at = now

    await log_action(
        db,
        action="billing.grace_period.recovered",
        org_id=org_id,
        target_type="subscription_grace_period",
        target_id=str(grace.id),
        extra={"recovered_at": now.isoformat()},
    )

    log.info("grace period recovered for org %s", org_id)
    return grace


async def expire_grace_period(
    db: AsyncSession, grace: SubscriptionGracePeriod
) -> None:
    """Expire a grace period and downgrade the org to FREE."""
    now = datetime.now(timezone.utc)
    grace.status = GracePeriodStatus.EXPIRED
    grace.expired_at = now

    # Downgrade org
    await db.execute(
        update(Organization)
        .where(Organization.id == grace.org_id)
        .values(plan=OrgPlan.FREE)
    )

    await log_action(
        db,
        action="billing.grace_period.expired",
        org_id=grace.org_id,
        target_type="subscription_grace_period",
        target_id=str(grace.id),
        extra={"downgraded_to": "FREE", "expired_at": now.isoformat()},
    )

    log.info("grace period expired for org %s, downgraded to FREE", grace.org_id)


async def record_notification(
    db: AsyncSession, grace: SubscriptionGracePeriod
) -> None:
    """Increment the notification counter for a grace period."""
    grace.notification_sent_count += 1
    grace.last_notification_at = datetime.now(timezone.utc)


async def get_expiring_grace_periods(db: AsyncSession) -> list[SubscriptionGracePeriod]:
    """Return active grace periods that have expired (past expires_at)."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(SubscriptionGracePeriod)
        .where(
            SubscriptionGracePeriod.status == GracePeriodStatus.ACTIVE,
            SubscriptionGracePeriod.expires_at <= now,
        )
    )
    return list(result.scalars().all())


async def get_notifiable_grace_periods(db: AsyncSession) -> list[SubscriptionGracePeriod]:
    """Return active grace periods that need a reminder notification."""
    result = await db.execute(
        select(SubscriptionGracePeriod)
        .where(
            SubscriptionGracePeriod.status == GracePeriodStatus.ACTIVE,
            SubscriptionGracePeriod.notification_sent_count < MAX_NOTIFICATIONS,
        )
    )
    return [gp for gp in result.scalars().all() if should_notify(gp)]
