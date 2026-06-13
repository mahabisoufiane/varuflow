"""Pure rules-based upsell trigger engine.

No DB, no HTTP, no FastAPI imports — only plain Python.
Callers pass in pre-fetched context objects; this module decides which
triggers are eligible and returns them ordered by priority.

Anti-annoyance contract (enforced in is_user_eligible):
- MEMBER role: never shown anything
- Trial users: only trial_lifecycle triggers
- Yearly subscriber ≤ 30 days old: no prompts
- Max 3 upsell prompts per rolling 7-day window
- Dismissed trigger: 7-day cooldown per trigger_id
- Max 1 modal placement per session (enforced client-side; service marks
  placement=modal for at most 1 result in evaluate_triggers)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Data Transfer Objects (pure Python — no SQLAlchemy / Pydantic)
# ---------------------------------------------------------------------------

@dataclass
class OrgData:
    id: str
    plan: str                           # "FREE" | "PRO" | "ENTERPRISE"
    created_at: datetime
    is_on_trial: bool
    trial_ends_at: datetime | None
    subscription_interval: str | None   # "month" | "year" | None
    subscription_started_at: datetime | None


@dataclass
class UserData:
    id: str
    role: str                           # "OWNER" | "ADMIN" | "MEMBER"


@dataclass
class UpsellContext:
    # Resource counters
    product_count: int = 0
    customer_count: int = 0
    user_count: int = 0
    invoice_count_this_month: int = 0
    warehouse_count: int = 0
    # Success signals
    invoices_paid_total: int = 0
    dunning_sent_count: int = 0
    # Time signals
    days_since_signup: int = 0
    trial_days_remaining: int = 0
    # Interaction signals
    locked_feature_attempted: str | None = None
    # Anti-annoyance state (pre-fetched by caller from upsell_events)
    recent_upsell_events: list[dict] = field(default_factory=list)
    # Number of times user was shown any upsell in last 7 days
    weekly_prompt_count: int = 0
    # Days since the org started its current paid subscription (0 if none)
    days_since_subscription: int = 0


@dataclass
class UpsellTrigger:
    id: str
    name: str
    condition: str          # human-readable description of when it fires
    message_template: str   # supports {plan}, {resource}, {count}, {limit}, {days}, {feature}
    cta: str
    target_tier: str        # "PRO" | "ENTERPRISE"
    placement: str          # "modal" | "banner" | "toast" | "inline"
    frequency_cap_days: int
    priority: int           # lower = higher priority


# ---------------------------------------------------------------------------
# Plan limits mirror (keep in sync with plan_limits.py)
# ---------------------------------------------------------------------------

_PLAN_LIMITS: dict[str, dict[str, int]] = {
    "FREE": {
        "max_products": 100,
        "max_customers": 200,
        "max_users": 3,
        "max_warehouses": 1,
        "max_invoices_per_month": 50,
    },
    "PRO": {
        "max_products": 2_000,
        "max_customers": 5_000,
        "max_users": 20,
        "max_warehouses": 5,
        "max_invoices_per_month": 500,
    },
}

_WARNING_THRESHOLD = 0.80
_UNLIMITED = -1


def _approaching(current: int, plan: str, resource: str) -> bool:
    limits = _PLAN_LIMITS.get(plan, {})
    limit = limits.get(resource, _UNLIMITED)
    if limit == _UNLIMITED or limit <= 0:
        return False
    return current / limit >= _WARNING_THRESHOLD and current < limit


def _at_limit(current: int, plan: str, resource: str) -> bool:
    limits = _PLAN_LIMITS.get(plan, {})
    limit = limits.get(resource, _UNLIMITED)
    if limit == _UNLIMITED or limit <= 0:
        return False
    return current >= limit


# ---------------------------------------------------------------------------
# Trigger definitions
# ---------------------------------------------------------------------------

ALL_TRIGGERS: list[UpsellTrigger] = [
    # 1. Limit approaching (≥80%, <100%)
    UpsellTrigger(
        id="limit_approaching",
        name="Limit Approaching",
        condition="Any resource is at ≥80% of the plan limit",
        message_template=(
            "You're getting close to your {plan} plan limit for {resource} "
            "({count}/{limit}). Upgrade to PRO to keep growing."
        ),
        cta="See PRO plans",
        target_tier="PRO",
        placement="banner",
        frequency_cap_days=3,
        priority=2,
    ),
    # 2. Limit hit (≥100%)
    UpsellTrigger(
        id="limit_hit",
        name="Limit Reached",
        condition="Any resource is at or over the plan limit",
        message_template=(
            "You've reached your {plan} plan limit for {resource}. "
            "Upgrade to PRO to add more."
        ),
        cta="Upgrade now",
        target_tier="PRO",
        placement="modal",
        frequency_cap_days=1,
        priority=1,
    ),
    # 3. Locked feature clicked
    UpsellTrigger(
        id="locked_feature_clicked",
        name="Locked Feature Clicked",
        condition="User attempted to use a feature locked by their plan",
        message_template=(
            "{feature} is a PRO feature. Upgrade to unlock it and "
            "get access to all advanced tools."
        ),
        cta="Unlock {feature}",
        target_tier="PRO",
        placement="modal",
        frequency_cap_days=2,
        priority=1,
    ),
    # 4. Success milestone
    UpsellTrigger(
        id="success_milestone",
        name="Success Milestone",
        condition="User has sent 10+ paid invoices — clear product-market fit signal",
        message_template=(
            "You've processed {count} invoices on Varuflow — great momentum! "
            "PRO removes all limits and unlocks automation tools."
        ),
        cta="Upgrade to PRO",
        target_tier="PRO",
        placement="toast",
        frequency_cap_days=14,
        priority=4,
    ),
    # 5. Pain pattern detected
    UpsellTrigger(
        id="pain_pattern_detected",
        name="Pain Pattern: Dunning",
        condition="User has sent 3+ dunning reminders — cash-flow pain",
        message_template=(
            "Chasing overdue invoices manually? PRO includes automatic "
            "dunning sequences that collect payments while you sleep."
        ),
        cta="Automate dunning",
        target_tier="PRO",
        placement="banner",
        frequency_cap_days=7,
        priority=3,
    ),
    # 6. Lifecycle day trigger (day 3, 7, 14)
    UpsellTrigger(
        id="lifecycle_day",
        name="Lifecycle Day Nudge",
        condition="Org is on day 3, 7, or 14 after signup",
        message_template=(
            "You've been using Varuflow for {days} days. "
            "Upgrade to PRO to remove all usage limits and keep growing."
        ),
        cta="View PRO plans",
        target_tier="PRO",
        placement="banner",
        frequency_cap_days=3,
        priority=5,
    ),
    # 7. AI feature glimpse
    UpsellTrigger(
        id="ai_feature_glimpse",
        name="AI Feature Glimpse",
        condition="FREE plan user has used AI queries — show value of more",
        message_template=(
            "You've been using AI queries. PRO gives you 10× more AI calls "
            "per day plus AI-generated product descriptions and price suggestions."
        ),
        cta="Unlock AI PRO",
        target_tier="PRO",
        placement="inline",
        frequency_cap_days=7,
        priority=6,
    ),
    # 8. Competitive FOMO
    UpsellTrigger(
        id="competitive_fomo",
        name="Competitive FOMO",
        condition="Org has 5+ customers — they're likely comparing tools",
        message_template=(
            "Top wholesalers using Varuflow PRO process 3× more invoices per month. "
            "Don't let competitors get ahead — upgrade today."
        ),
        cta="See what PRO unlocks",
        target_tier="PRO",
        placement="banner",
        frequency_cap_days=14,
        priority=7,
    ),
    # 9. Mobile specific
    UpsellTrigger(
        id="mobile_specific",
        name="Mobile Power User",
        condition="PRO user on FREE plan — mobile features teaser",
        message_template=(
            "PRO unlocks the Varuflow mobile field app: delivery routes, "
            "digital signatures, and offline POS."
        ),
        cta="Go mobile with PRO",
        target_tier="PRO",
        placement="inline",
        frequency_cap_days=14,
        priority=8,
    ),
    # 10. Trial lifecycle
    UpsellTrigger(
        id="trial_lifecycle",
        name="Trial Lifecycle",
        condition="Trial is active and ending within 7 days",
        message_template=(
            "Your PRO trial ends in {days} day(s). "
            "Subscribe now to keep all your data and features."
        ),
        cta="Subscribe to PRO",
        target_tier="PRO",
        placement="banner",
        frequency_cap_days=1,
        priority=1,
    ),
]

# Quick lookup by id
_TRIGGER_BY_ID: dict[str, UpsellTrigger] = {t.id: t for t in ALL_TRIGGERS}

# ---------------------------------------------------------------------------
# Core eligibility check
# ---------------------------------------------------------------------------

_MAX_WEEKLY_PROMPTS = 3
_DISMISS_COOLDOWN_DAYS = 7


def _days_between(a: datetime, b: datetime) -> int:
    """Return number of whole days from a to b (b - a)."""
    delta = b - a
    return int(delta.total_seconds() / 86400)


def is_user_eligible(
    user: UserData,
    trigger: UpsellTrigger,
    ctx: UpsellContext,
    now: datetime,
) -> bool:
    """Return True if the user/org passes all anti-annoyance rules for this trigger."""
    # Rule 1: MEMBERs never see upsells
    if user.role == "MEMBER":
        return False

    # Rule 2: Weekly cap
    if ctx.weekly_prompt_count >= _MAX_WEEKLY_PROMPTS:
        return False

    # Check per-trigger events
    for event in ctx.recent_upsell_events:
        if event.get("trigger_id") != trigger.id:
            continue
        # Rule 3: Frequency cap — shown_at within cap window
        shown_at = event.get("shown_at")
        if shown_at:
            if isinstance(shown_at, str):
                shown_at = datetime.fromisoformat(shown_at)
            if (now - shown_at).total_seconds() / 86400 < trigger.frequency_cap_days:
                return False
        # Rule 4: Dismissed trigger — 7-day cooldown
        dismissed_at = event.get("dismissed_at")
        if dismissed_at:
            if isinstance(dismissed_at, str):
                dismissed_at = datetime.fromisoformat(dismissed_at)
            if (now - dismissed_at).total_seconds() / 86400 < _DISMISS_COOLDOWN_DAYS:
                return False

    return True


# ---------------------------------------------------------------------------
# Per-trigger condition evaluation
# ---------------------------------------------------------------------------

def _condition_met(
    trigger: UpsellTrigger,
    org: OrgData,
    ctx: UpsellContext,
    now: datetime,
) -> bool:
    """Check the business condition for a trigger (ignores anti-annoyance rules)."""
    tid = trigger.id

    if tid == "limit_approaching":
        return (
            _approaching(ctx.product_count, org.plan, "max_products")
            or _approaching(ctx.customer_count, org.plan, "max_customers")
            or _approaching(ctx.user_count, org.plan, "max_users")
            or _approaching(ctx.warehouse_count, org.plan, "max_warehouses")
            or _approaching(ctx.invoice_count_this_month, org.plan, "max_invoices_per_month")
        )

    if tid == "limit_hit":
        return (
            _at_limit(ctx.product_count, org.plan, "max_products")
            or _at_limit(ctx.customer_count, org.plan, "max_customers")
            or _at_limit(ctx.user_count, org.plan, "max_users")
            or _at_limit(ctx.warehouse_count, org.plan, "max_warehouses")
            or _at_limit(ctx.invoice_count_this_month, org.plan, "max_invoices_per_month")
        )

    if tid == "locked_feature_clicked":
        return ctx.locked_feature_attempted is not None

    if tid == "success_milestone":
        return ctx.invoices_paid_total >= 10 and org.plan == "FREE"

    if tid == "pain_pattern_detected":
        return ctx.dunning_sent_count >= 3 and org.plan == "FREE"

    if tid == "lifecycle_day":
        return ctx.days_since_signup in (3, 7, 14) and org.plan == "FREE"

    if tid == "ai_feature_glimpse":
        # Only for FREE plan orgs that have used AI at all (proxy: dunning or invoices exist)
        return org.plan == "FREE" and ctx.invoices_paid_total > 0

    if tid == "competitive_fomo":
        return ctx.customer_count >= 5 and org.plan == "FREE"

    if tid == "mobile_specific":
        return org.plan == "FREE" and ctx.invoices_paid_total >= 5

    if tid == "trial_lifecycle":
        return org.is_on_trial and 0 < ctx.trial_days_remaining <= 7

    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_triggers(
    org: OrgData,
    user: UserData,
    ctx: UpsellContext,
    now: datetime | None = None,
) -> list[UpsellTrigger]:
    """Return list of eligible triggers, ordered by priority (ascending = most urgent first).

    Anti-annoyance rules applied:
    - MEMBER role → empty list
    - Trial users → only trial_lifecycle triggers
    - Yearly subscriber ≤ 30 days old → empty list
    - At most 1 modal per result set (highest-priority modal only)
    - Weekly cap / dismiss cooldown / frequency cap via is_user_eligible
    """
    if now is None:
        now = datetime.now(tz=timezone.utc)

    # MEMBER never sees upsells
    if user.role == "MEMBER":
        return []

    # Yearly subscriber in honeymoon period
    if (
        org.subscription_interval == "year"
        and org.subscription_started_at is not None
        and ctx.days_since_subscription <= 30
    ):
        return []

    results: list[UpsellTrigger] = []
    modal_used = False

    for trigger in sorted(ALL_TRIGGERS, key=lambda t: t.priority):
        # Trial users only see trial_lifecycle
        if org.is_on_trial and trigger.id != "trial_lifecycle":
            continue

        if not _condition_met(trigger, org, ctx, now):
            continue

        if not is_user_eligible(user, trigger, ctx, now):
            continue

        # At most 1 modal per evaluate call
        if trigger.placement == "modal":
            if modal_used:
                continue
            modal_used = True

        results.append(trigger)

    return results


def format_message(trigger: UpsellTrigger, variables: dict[str, str]) -> str:
    """Interpolate {placeholders} in message_template and cta."""
    return trigger.message_template.format_map(_SafeDict(variables))


def format_cta(trigger: UpsellTrigger, variables: dict[str, str]) -> str:
    return trigger.cta.format_map(_SafeDict(variables))


class _SafeDict(dict):
    """dict subclass that returns '{key}' for missing keys instead of raising KeyError."""
    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"
