"""Upsell trigger engine — REST layer.

GET  /api/upsells/pending     → evaluate which triggers to show the user
POST /api/upsells/shown       → record an impression
POST /api/upsells/clicked     → record a CTA click
POST /api/upsells/dismissed   → record a dismissal

All write endpoints are fire-and-forget from the client's perspective: they
always return 204 even when an event is not found or already closed, so the
frontend never has to handle error cases for analytics bookkeeping.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.features.inventory.models import Product, Warehouse
from app.features.invoicing.models import Customer, Invoice
from app.features.auth.organization import Organization
from app.features.marketing.upsell import UpsellEvent
from app.services.audit import log_action
from app.services.upsells import (
    OrgData,
    UpsellContext,
    UserData,
    evaluate_triggers,
    format_cta,
    format_message,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/upsells", tags=["upsells"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ids(ctx: tuple) -> tuple[uuid.UUID, uuid.UUID]:
    user_info, member = ctx
    uid = user_info.get("user_id") or user_info.get("sub")
    return member.org_id, uid if isinstance(uid, uuid.UUID) else uuid.UUID(str(uid))


def _member_role(ctx: tuple) -> str:
    _user_info, member = ctx
    return member.role.value if hasattr(member.role, "value") else str(member.role)


async def _get_org(org_id: uuid.UUID, db: AsyncSession) -> Organization:
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


async def _build_context(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    org: Organization,
    db: AsyncSession,
    locked_feature: str | None,
) -> UpsellContext:
    """Fetch all counts needed by the upsell rules engine."""
    now = datetime.now(tz=timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    # Resource counts
    r_products = await db.execute(
        select(func.count()).select_from(Product).where(
            Product.org_id == org_id, Product.deleted_at.is_(None)
        )
    )
    r_customers = await db.execute(
        select(func.count()).select_from(Customer).where(
            Customer.org_id == org_id, Customer.deleted_at.is_(None)
        )
    )
    r_warehouses = await db.execute(
        select(func.count()).select_from(Warehouse).where(Warehouse.org_id == org_id)
    )
    r_invoices_month = await db.execute(
        select(func.count()).select_from(Invoice).where(
            Invoice.org_id == org_id,
            Invoice.created_at >= month_start,
            Invoice.deleted_at.is_(None),
        )
    )
    r_invoices_paid = await db.execute(
        select(func.count()).select_from(Invoice).where(
            Invoice.org_id == org_id,
            Invoice.status == "PAID",
            Invoice.deleted_at.is_(None),
        )
    )

    # Recent upsell events for this user (last 30 days for cooldown checks)
    r_events = await db.execute(
        select(UpsellEvent).where(
            UpsellEvent.org_id == org_id,
            UpsellEvent.user_id == user_id,
            UpsellEvent.shown_at >= now - timedelta(days=30),
        )
    )
    raw_events = r_events.scalars().all()

    # Build recent_upsell_events list for the service
    recent: list[dict] = [
        {
            "trigger_id": e.trigger_id,
            "shown_at": e.shown_at,
            "dismissed_at": e.dismissed_at,
            "converted_at": e.converted_at,
        }
        for e in raw_events
    ]

    # Weekly prompt count
    weekly_count = sum(
        1 for e in raw_events
        if e.shown_at >= week_ago
    )

    # Days since signup
    days_since_signup = (now - org.created_at.replace(tzinfo=timezone.utc)).days if org.created_at else 0

    # Days since subscription started
    days_since_sub = 0
    if org.trial_converted_at:
        days_since_sub = (now - org.trial_converted_at.replace(tzinfo=timezone.utc)).days

    # Trial days remaining
    trial_days_remaining = 0
    if org.trial_ends_at and not org.trial_converted_at:
        delta = org.trial_ends_at.replace(tzinfo=timezone.utc) - now
        trial_days_remaining = max(0, delta.days)

    return UpsellContext(
        product_count=r_products.scalar() or 0,
        customer_count=r_customers.scalar() or 0,
        user_count=0,  # filled cheaply via org member count if needed; 0 is safe default
        invoice_count_this_month=r_invoices_month.scalar() or 0,
        warehouse_count=r_warehouses.scalar() or 0,
        invoices_paid_total=r_invoices_paid.scalar() or 0,
        dunning_sent_count=0,  # dunning module tracks separately; 0 is safe
        days_since_signup=days_since_signup,
        trial_days_remaining=trial_days_remaining,
        locked_feature_attempted=locked_feature,
        recent_upsell_events=recent,
        weekly_prompt_count=weekly_count,
        days_since_subscription=days_since_sub,
    )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PendingUpsellsQuery(BaseModel):
    locked_feature: str | None = Field(default=None, max_length=100)


class UpsellTriggerResponse(BaseModel):
    id: str
    name: str
    message: str
    cta: str
    target_tier: str
    placement: str
    priority: int


class UpsellEventIn(BaseModel):
    trigger_id: str = Field(..., max_length=80)
    placement: str = Field(default="modal", max_length=20)
    target_tier: str = Field(default="PRO", max_length=20)
    ab_variant: str | None = Field(default=None, max_length=20)
    upsell_event_id: uuid.UUID | None = Field(default=None)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/pending", response_model=list[UpsellTriggerResponse])
async def get_pending_upsells(
    locked_feature: str | None = None,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return which upsell triggers are currently eligible for the requesting user."""
    try:
        org_id, user_id = _ids(ctx)
        role = _member_role(ctx)

        org = await _get_org(org_id, db)

        upsell_ctx = await _build_context(org_id, user_id, org, db, locked_feature)

        is_on_trial = getattr(org, "is_on_trial", False)
        trial_ends_at = getattr(org, "trial_ends_at", None)
        sub_started_at = getattr(org, "subscription_started_at", None)
        sub_interval = getattr(org, "subscription_interval", None)

        org_data = OrgData(
            id=str(org.id),
            plan=org.plan if isinstance(org.plan, str) else org.plan.value,
            created_at=org.created_at.replace(tzinfo=timezone.utc) if org.created_at else datetime.now(tz=timezone.utc),
            is_on_trial=bool(is_on_trial),
            trial_ends_at=trial_ends_at.replace(tzinfo=timezone.utc) if trial_ends_at else None,
            subscription_interval=str(sub_interval) if sub_interval else None,
            subscription_started_at=sub_started_at.replace(tzinfo=timezone.utc) if sub_started_at else None,
        )
        user_data = UserData(id=str(user_id), role=role)

        triggers = evaluate_triggers(org_data, user_data, upsell_ctx)

        results = []
        for t in triggers:
            variables = {
                "plan": org_data.plan,
                "days": str(upsell_ctx.trial_days_remaining or upsell_ctx.days_since_signup),
                "count": str(upsell_ctx.invoices_paid_total),
                "feature": locked_feature or "",
                "resource": _first_approaching_resource(upsell_ctx, org_data.plan),
                "limit": _first_approaching_limit(upsell_ctx, org_data.plan),
            }
            results.append(
                UpsellTriggerResponse(
                    id=t.id,
                    name=t.name,
                    message=format_message(t, variables),
                    cta=format_cta(t, variables),
                    target_tier=t.target_tier,
                    placement=t.placement,
                    priority=t.priority,
                )
            )
        return results
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"get_pending_upsells failed: {e}", extra={"org_id": str(org_id) if 'org_id' in dir() else "unknown"})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/shown", status_code=204)
async def record_upsell_shown(
    body: UpsellEventIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Record that an upsell was shown to the user (impression)."""
    try:
        org_id, user_id = _ids(ctx)
        event = UpsellEvent(
            org_id=org_id,
            user_id=user_id,
            trigger_id=body.trigger_id,
            placement=body.placement,
            target_tier=body.target_tier,
            ab_variant=body.ab_variant,
        )
        db.add(event)
        await db.commit()
    except Exception as e:
        log.error(f"record_upsell_shown failed: {e}")
        await db.rollback()
        # Fire-and-forget — never raise to client


@router.post("/clicked", status_code=204)
async def record_upsell_clicked(
    body: UpsellEventIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Record that a user clicked the upsell CTA."""
    try:
        org_id, user_id = _ids(ctx)
        # Find most recent unclicked event for this trigger
        result = await db.execute(
            select(UpsellEvent).where(
                UpsellEvent.org_id == org_id,
                UpsellEvent.user_id == user_id,
                UpsellEvent.trigger_id == body.trigger_id,
                UpsellEvent.clicked_at.is_(None),
            ).order_by(UpsellEvent.shown_at.desc()).limit(1)
        )
        event = result.scalar_one_or_none()
        if event:
            event.clicked_at = datetime.now(tz=timezone.utc)
            await db.commit()
            await log_action(
                db,
                action="upsell_clicked",
                org_id=org_id,
                actor_user_id=user_id,
                target_type="upsell_trigger",
                target_id=str(event.id),
                request=request,
                extra={"trigger_id": body.trigger_id},
            )
    except Exception as e:
        log.error(f"record_upsell_clicked failed: {e}")
        await db.rollback()


@router.post("/dismissed", status_code=204)
async def record_upsell_dismissed(
    body: UpsellEventIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Record that a user dismissed an upsell."""
    try:
        org_id, user_id = _ids(ctx)
        result = await db.execute(
            select(UpsellEvent).where(
                UpsellEvent.org_id == org_id,
                UpsellEvent.user_id == user_id,
                UpsellEvent.trigger_id == body.trigger_id,
                UpsellEvent.dismissed_at.is_(None),
            ).order_by(UpsellEvent.shown_at.desc()).limit(1)
        )
        event = result.scalar_one_or_none()
        if event:
            event.dismissed_at = datetime.now(tz=timezone.utc)
            await db.commit()
    except Exception as e:
        log.error(f"record_upsell_dismissed failed: {e}")
        await db.rollback()


# ---------------------------------------------------------------------------
# Private helpers for variable interpolation
# ---------------------------------------------------------------------------

_RESOURCE_LABELS = {
    "max_products": "products",
    "max_customers": "customers",
    "max_users": "users",
    "max_warehouses": "warehouses",
    "max_invoices_per_month": "invoices this month",
}

_PLAN_LIMITS: dict[str, dict[str, int]] = {
    "FREE": {"max_products": 100, "max_customers": 200, "max_users": 3, "max_warehouses": 1, "max_invoices_per_month": 50},
    "PRO": {"max_products": 2000, "max_customers": 5000, "max_users": 20, "max_warehouses": 5, "max_invoices_per_month": 500},
}
_RESOURCE_COUNTS = {
    "max_products": lambda c: c.product_count,
    "max_customers": lambda c: c.customer_count,
    "max_users": lambda c: c.user_count,
    "max_warehouses": lambda c: c.warehouse_count,
    "max_invoices_per_month": lambda c: c.invoice_count_this_month,
}
_THRESHOLD = 0.80


def _first_approaching_resource(ctx: UpsellContext, plan: str) -> str:
    limits = _PLAN_LIMITS.get(plan, {})
    for resource, limit in limits.items():
        count_fn = _RESOURCE_COUNTS.get(resource)
        if count_fn and limit > 0:
            count = count_fn(ctx)
            if count / limit >= _THRESHOLD:
                return _RESOURCE_LABELS.get(resource, resource)
    return "resources"


def _first_approaching_limit(ctx: UpsellContext, plan: str) -> str:
    limits = _PLAN_LIMITS.get(plan, {})
    for resource, limit in limits.items():
        count_fn = _RESOURCE_COUNTS.get(resource)
        if count_fn and limit > 0:
            count = count_fn(ctx)
            if count / limit >= _THRESHOLD:
                return str(limit)
    return "your limit"
