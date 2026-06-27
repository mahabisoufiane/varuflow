"""PostHog product analytics service — server-side event tracking.

Design principles:
- All functions are async (FastAPI-compatible) and NEVER raise.
- A try/except wraps every PostHog call so tracking failures cannot
  block or crash business logic.
- The client is a lazy module-level singleton; it is only created once
  POSTHOG_API_KEY is present and ENV != development.
- Functions are fire-and-forget: they flush asynchronously via PostHog's
  own background thread (sync_mode=False).  No await needed for speed.

Usage:
    from app.services.analytics import track_invoice_created
    await track_invoice_created(user_id=str(member.user_id), org_id=str(org.id), is_first_invoice=False)

Event naming convention — snake_case verbs matching frontend constants:
    signup_completed, trial_started, invoice_created, pos_sale, subscription_changed
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

# ── Lazy PostHog singleton ────────────────────────────────────────────────────

_posthog_client = None   # posthog module reference, or None if disabled
_client_ready   = False  # set once after first successful init attempt


def _get_client():
    """Return the posthog module configured as a client, or None.

    Called on every track call.  The initialization is idempotent — after
    the first call (failed or successful), _client_ready is True and we
    skip re-initialization.
    """
    global _posthog_client, _client_ready
    if _client_ready:
        return _posthog_client

    _client_ready = True  # mark even on failure so we don't retry every call

    try:
        from app.config import settings  # local import avoids circular startup

        # Disabled for development and when no API key is configured
        if settings.ENV == "development" or not settings.POSTHOG_API_KEY:
            return None

        import posthog as _ph
        _ph.project_api_key = settings.POSTHOG_API_KEY
        _ph.host            = settings.POSTHOG_HOST
        _ph.sync_mode       = False  # fire-and-forget; background flush thread
        _ph.disabled        = False
        _posthog_client = _ph
        log.info('"event":"posthog_initialized","host":"%s"', settings.POSTHOG_HOST)
    except Exception as exc:  # noqa: BLE001
        log.warning('"event":"posthog_init_failed","error":"%s"', exc)
        _posthog_client = None

    return _posthog_client


# ── Event constants ───────────────────────────────────────────────────────────
# Keep in sync with frontend/src/lib/analytics.ts

SIGNUP_STARTED              = "signup_started"
SIGNUP_COMPLETED            = "signup_completed"
TRIAL_STARTED               = "trial_started"
ONBOARDING_STEP_COMPLETED   = "onboarding_step_completed"
FIRST_INVOICE_CREATED       = "first_invoice_created"
INVOICE_CREATED             = "invoice_created"
FIRST_POS_SALE              = "first_pos_sale"
POS_SALE                    = "pos_sale"
UPSELL_SHOWN                = "upsell_shown"
UPSELL_CLICKED              = "upsell_clicked"
UPSELL_DISMISSED            = "upsell_dismissed"
UPSELL_CONVERTED            = "upsell_converted"
SUBSCRIPTION_STARTED        = "subscription_started"
SUBSCRIPTION_UPGRADED       = "subscription_upgraded"
SUBSCRIPTION_DOWNGRADED     = "subscription_downgraded"
SUBSCRIPTION_CANCELED       = "subscription_canceled"
FEATURE_USED                = "feature_used"
AI_QUERY_MADE               = "ai_query_made"
LIMIT_WARNING_SHOWN         = "limit_warning_shown"
LIMIT_BLOCKED_SHOWN         = "limit_blocked_shown"


# ── Core primitives ───────────────────────────────────────────────────────────

async def track_event(
    distinct_id: str,
    event: str,
    properties: dict[str, Any] | None = None,
) -> None:
    """Fire a PostHog event.  Never raises."""
    try:
        client = _get_client()
        if client is None:
            return
        client.capture(
            distinct_id=distinct_id,
            event=event,
            properties=properties or {},
        )
    except Exception as exc:  # noqa: BLE001
        log.warning('"event":"posthog_track_failed","name":"%s","error":"%s"', event, exc)


async def identify_user(
    user_id: str,
    traits: dict[str, Any],
) -> None:
    """Associate properties with a user.  PII fields must be omitted by callers."""
    try:
        client = _get_client()
        if client is None:
            return
        client.identify(distinct_id=user_id, properties=traits)
    except Exception as exc:  # noqa: BLE001
        log.warning('"event":"posthog_identify_failed","user_id":"%s","error":"%s"', user_id, exc)


# ── High-level business events ────────────────────────────────────────────────

async def track_signup(
    user_id: str,
    org_name: str,
    plan: str,
) -> None:
    """Emits signup_completed with org-level traits.

    Never passes the org_name directly as a posthog property — it is used
    only to call identify() and set the group-level org name.
    """
    await identify_user(user_id, {"plan": plan})
    await track_event(
        distinct_id=user_id,
        event=SIGNUP_COMPLETED,
        properties={"plan": plan},
    )


async def track_trial_start(
    user_id: str,
    org_id: str,
    plan: str,
    source: str | None = None,
) -> None:
    """Emits trial_started.  Called from trial router POST /api/trial/start."""
    await track_event(
        distinct_id=user_id,
        event=TRIAL_STARTED,
        properties={
            "org_id":     org_id,
            "trial_plan": plan,
            "source":     source or "direct",
        },
    )


async def track_invoice_created(
    user_id: str,
    org_id: str,
    is_first_invoice: bool = False,
) -> None:
    """Emits invoice_created (and first_invoice_created on first invoice)."""
    props = {"org_id": org_id}
    if is_first_invoice:
        await track_event(distinct_id=user_id, event=FIRST_INVOICE_CREATED, properties=props)
    await track_event(distinct_id=user_id, event=INVOICE_CREATED, properties=props)


async def track_pos_sale(
    user_id: str,
    org_id: str,
    total: float,
    is_first_sale: bool = False,
) -> None:
    """Emits pos_sale (and first_pos_sale on first sale)."""
    props = {"org_id": org_id, "total": total}
    if is_first_sale:
        await track_event(distinct_id=user_id, event=FIRST_POS_SALE, properties=props)
    await track_event(distinct_id=user_id, event=POS_SALE, properties=props)


async def track_subscription_changed(
    user_id: str,
    org_id: str,
    event_type: str,   # SUBSCRIPTION_STARTED | _UPGRADED | _DOWNGRADED | _CANCELED
    tier: str,
    interval: str | None = None,  # "month" | "year" | None
) -> None:
    """Emits any subscription lifecycle event.

    event_type must be one of the SUBSCRIPTION_* constants above.
    """
    await track_event(
        distinct_id=user_id,
        event=event_type,
        properties={
            "org_id":   org_id,
            "tier":     tier,
            "interval": interval or "unknown",
        },
    )


async def track_feature_used(
    user_id: str,
    org_id: str,
    feature: str,
) -> None:
    """Emits feature_used.  Used for the top-30 feature engagement report."""
    await track_event(
        distinct_id=user_id,
        event=FEATURE_USED,
        properties={"org_id": org_id, "feature": feature},
    )


async def track_ai_query(
    user_id: str,
    org_id: str,
) -> None:
    """Emits ai_query_made.  Called from integrations.py /api/integrations/ai/chat."""
    await track_event(
        distinct_id=user_id,
        event=AI_QUERY_MADE,
        properties={"org_id": org_id},
    )


async def track_upsell(
    user_id: str,
    org_id: str,
    action: str,        # "shown" | "clicked" | "dismissed" | "converted"
    placement: str,
    tier_offered: str,
    trigger: str | None = None,
) -> None:
    """Emits upsell_<action> for the upgrade funnel."""
    event_map = {
        "shown":     UPSELL_SHOWN,
        "clicked":   UPSELL_CLICKED,
        "dismissed": UPSELL_DISMISSED,
        "converted": UPSELL_CONVERTED,
    }
    event = event_map.get(action)
    if not event:
        return
    await track_event(
        distinct_id=user_id,
        event=event,
        properties={
            "org_id":      org_id,
            "placement":   placement,
            "tier_offered": tier_offered,
            "trigger":     trigger or "manual",
        },
    )


async def track_limit_shown(
    user_id: str,
    org_id: str,
    blocked: bool,
    resource: str,
    plan: str,
) -> None:
    """Emits limit_warning_shown or limit_blocked_shown.

    Called from plan_check middleware after detecting 80%/100% usage.
    """
    event = LIMIT_BLOCKED_SHOWN if blocked else LIMIT_WARNING_SHOWN
    await track_event(
        distinct_id=user_id,
        event=event,
        properties={
            "org_id":   org_id,
            "resource": resource,
            "plan":     plan,
        },
    )
