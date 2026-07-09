"""Plan limits enforcement — pure module, no DB calls.

All functions take plain values (OrgPlan enum + integer counts) so they
can be unit-tested without any database or AsyncSession fixture.

Tier mapping:
  OrgPlan.FREE       → free-only (dashboard + settings)
  OrgPlan.PRO        → paid tiers (Starter 499 SEK + Professional 1490 SEK)
  OrgPlan.ENTERPRISE → unlimited (-1 sentinel), contact sales (3990 SEK)

Both Starter and Professional map to OrgPlan.PRO in the DB; Stripe price ID
determines the billing amount, but feature/module access is identical.

Limit sentinel:
  -1  means unlimited; get_limit() returns None for unlimited.

Warning threshold:
  80 % usage triggers ApproachingLimitError.
  100 % usage triggers LimitExceededError.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.features.auth.organization import OrgPlan

# ── Resource keys ────────────────────────────────────────────────────────────
# These string constants are used as dictionary keys in PLAN_LIMITS and as
# the `resource` argument to check_limit / get_limit.

RESOURCE_USERS             = "max_users"
RESOURCE_WAREHOUSES        = "max_warehouses"
RESOURCE_PRODUCTS          = "max_products"
RESOURCE_INVOICES_PER_MONTH = "max_invoices_per_month"
RESOURCE_CUSTOMERS         = "max_customers"
RESOURCE_STORAGE_GB        = "max_storage_gb"
RESOURCE_AI_CALLS_PER_DAY  = "ai_calls_per_day"

# Sentinel value meaning "no limit" in the PLAN_LIMITS dict.
_UNLIMITED = -1

# ── Feature flag keys ─────────────────────────────────────────────────────────
FEATURE_API_WEBHOOKS     = "api_webhooks"
FEATURE_WHITE_LABEL      = "white_label"
FEATURE_MULTI_WAREHOUSE  = "multi_warehouse"
FEATURE_ESIGN            = "esign"
FEATURE_ADVANCED_REPORTS = "advanced_reports"
FEATURE_FORTNOX_SYNC     = "fortnox_sync"
FEATURE_ZAPIER           = "zapier"
FEATURE_PRIORITY_SUPPORT = "priority_support"
FEATURE_AI_CHAT          = "ai_chat"
FEATURE_LOYALTY          = "loyalty"
FEATURE_FAMILY_GROUPS    = "family_groups"
FEATURE_PORTAL_CUSTOM    = "portal_customisation"
FEATURE_MULTI_ENTITY     = "multi_entity"
FEATURE_IP_ALLOWLIST     = "ip_allowlist"
FEATURE_AUDIT_LOG        = "audit_log"

# ── Tier definitions ─────────────────────────────────────────────────────────
# Each tier is a dict of resource_key → int limit (-1 = unlimited).

# FREE plan — showcase/trial only. Limits are intentionally tight to drive
# upgrade; matches the 14-day PRO trial window.
_STARTER: dict[str, int] = {
    RESOURCE_USERS:              3,
    RESOURCE_WAREHOUSES:         1,
    RESOURCE_PRODUCTS:          100,
    RESOURCE_INVOICES_PER_MONTH: 20,
    RESOURCE_CUSTOMERS:          30,
    RESOURCE_STORAGE_GB:          1,
    RESOURCE_AI_CALLS_PER_DAY:    0,
}

# PRO plan — covers both Starter (499 SEK) and Professional (1490 SEK) tiers.
# Limits sized for a Nordic wholesale company with 1–30 staff.
_PRO: dict[str, int] = {
    RESOURCE_USERS:              20,
    RESOURCE_WAREHOUSES:          5,
    RESOURCE_PRODUCTS:        25_000,
    RESOURCE_INVOICES_PER_MONTH: _UNLIMITED,
    RESOURCE_CUSTOMERS:        _UNLIMITED,
    RESOURCE_STORAGE_GB:          20,
    RESOURCE_AI_CALLS_PER_DAY:   200,
}

_ENTERPRISE: dict[str, int] = {
    RESOURCE_USERS:              _UNLIMITED,
    RESOURCE_WAREHOUSES:         _UNLIMITED,
    RESOURCE_PRODUCTS:           _UNLIMITED,
    RESOURCE_INVOICES_PER_MONTH: _UNLIMITED,
    RESOURCE_CUSTOMERS:          _UNLIMITED,
    RESOURCE_STORAGE_GB:         _UNLIMITED,
    RESOURCE_AI_CALLS_PER_DAY:   _UNLIMITED,
}

# Feature flags enabled per tier (additive; higher tiers include all lower).
_STARTER_FEATURES: frozenset[str] = frozenset()   # free plan has no premium features

_PRO_FEATURES: frozenset[str] = frozenset({
    FEATURE_MULTI_WAREHOUSE,
    FEATURE_ESIGN,
    FEATURE_ADVANCED_REPORTS,
    FEATURE_FORTNOX_SYNC,      # key Nordic differentiator — available on all paid tiers
    FEATURE_ZAPIER,
    FEATURE_AI_CHAT,
    FEATURE_PORTAL_CUSTOM,
    FEATURE_AUDIT_LOG,
    FEATURE_IP_ALLOWLIST,
    FEATURE_LOYALTY,
})

_ENTERPRISE_FEATURES: frozenset[str] = _PRO_FEATURES | frozenset({
    FEATURE_API_WEBHOOKS,
    FEATURE_WHITE_LABEL,
    FEATURE_PRIORITY_SUPPORT,
    FEATURE_MULTI_ENTITY,
})

# Master lookup keyed on OrgPlan string values so the module stays importable
# even before the OrgPlan enum is imported (avoids circular-import at module
# load time).
PLAN_LIMITS: dict[str, dict[str, int]] = {
    "FREE":       _STARTER,
    "PRO":        _PRO,
    "ENTERPRISE": _ENTERPRISE,
}

PLAN_FEATURES: dict[str, frozenset[str]] = {
    "FREE":       _STARTER_FEATURES,
    "PRO":        _PRO_FEATURES,
    "ENTERPRISE": _ENTERPRISE_FEATURES,
}

# ── Module-to-plan mapping ───────────────────────────────────────────────────
# Defines which app modules are available per plan tier.
# Used by require_module() middleware to gate route access.
PLAN_MODULES: dict[str, frozenset[str]] = {
    # Showcase only — FREE users see the product UI but cannot use any
    # operational modules. This drives upgrade conversions while still
    # letting prospects evaluate the UX before committing to a paid plan.
    "FREE": frozenset({
        "dashboard",   # read-only overview (no BI reports or drill-down)
        "settings",    # account & billing settings so they can upgrade
    }),
    # Full business operations suite — everything a scaling team needs.
    "PRO": frozenset({
        "dashboard",
        "analytics",   # BI dashboards, reports, forecasting, cohorts
        "pos",         # cash register + Z-reports + sessions
        "invoicing",
        "inventory",
        "crm",         # pipeline, leads, forecast, B2B hub
        "hr",          # employees, scheduling, timesheets, projects
        "finance",     # accounting, payroll, budget, CEO dashboard, reconciliation
        "ai",          # AI advisor, automations, workflows, email drafts
        "manufacturing",  # BOMs, work orders, production planning
        "settings",
    }),
    # Unlimited resources + platform features (white-label, API, multi-entity).
    "ENTERPRISE": frozenset({"*"}),
}

# Threshold at which an ApproachingLimitError is raised instead of blocking.
WARNING_THRESHOLD = 0.80


# ── Errors ────────────────────────────────────────────────────────────────────

@dataclass
class LimitStatus:
    """Return value of check_limit() — never raises itself."""
    allowed: bool
    percentage_used: float          # 0.0–1.0+; can exceed 1.0 when blocked
    message: str


class ApproachingLimitError(Exception):
    """Raised when usage is at or above WARNING_THRESHOLD but below 100 %.

    Callers may choose to surface a yellow warning banner without blocking.
    """
    def __init__(self, resource: str, current: int, limit: int, percentage: float) -> None:
        self.resource    = resource
        self.current     = current
        self.limit       = limit
        self.percentage  = percentage
        super().__init__(
            f"{resource}: {current}/{limit} ({percentage:.0%}) — approaching limit"
        )


class LimitExceededError(Exception):
    """Raised when usage has reached or exceeded 100 % of the plan limit."""
    def __init__(self, resource: str, current: int, limit: int) -> None:
        self.resource = resource
        self.current  = current
        self.limit    = limit
        super().__init__(f"{resource}: limit of {limit} reached (current: {current})")


# ── Public helpers ────────────────────────────────────────────────────────────

def get_limit(plan: "OrgPlan", resource: str) -> int | None:
    """Return the numeric limit for *resource* on *plan*.

    Returns ``None`` when the resource is unlimited for this plan.
    """
    plan_key = plan.value if hasattr(plan, "value") else str(plan)
    tier = PLAN_LIMITS.get(plan_key, _STARTER)
    value = tier.get(resource, 0)
    return None if value == _UNLIMITED else value


def is_feature_unlocked(plan: "OrgPlan", feature: str) -> bool:
    """Return True when *feature* is available on *plan*."""
    plan_key = plan.value if hasattr(plan, "value") else str(plan)
    allowed = PLAN_FEATURES.get(plan_key, _STARTER_FEATURES)
    return feature in allowed


def check_limit(
    plan: "OrgPlan",
    resource: str,
    current_count: int,
) -> LimitStatus:
    """Check whether *current_count* is within the plan limit for *resource*.

    Behaviour:
    - Unlimited plans always return ``LimitStatus(allowed=True, 0.0, "ok")``.
    - At < 80 % usage: returns ``LimitStatus(allowed=True, ...)``.
    - At ≥ 80 % and < 100 %: raises ``ApproachingLimitError``.
    - At ≥ 100 %: raises ``LimitExceededError``.

    The returned ``LimitStatus`` (when not raising) always reflects the
    true state; callers that only need a bool can inspect ``.allowed``.
    """
    limit = get_limit(plan, resource)

    # Unlimited — short-circuit.
    if limit is None:
        return LimitStatus(allowed=True, percentage_used=0.0, message="ok")

    if limit == 0:
        # Resource entirely locked for this plan.
        if current_count > 0:
            raise LimitExceededError(resource, current_count, 0)
        return LimitStatus(
            allowed=True,
            percentage_used=0.0,
            message=f"{resource} is not available on this plan",
        )

    pct = current_count / limit

    if pct >= 1.0:
        raise LimitExceededError(resource, current_count, limit)

    if pct >= WARNING_THRESHOLD:
        raise ApproachingLimitError(resource, current_count, limit, pct)

    return LimitStatus(
        allowed=True,
        percentage_used=pct,
        message=f"{current_count}/{limit} {resource} used",
    )
