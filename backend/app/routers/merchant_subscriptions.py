"""Merchant Subscription Billing router
Manages billing plans and customer subscriptions for Nordic wholesalers.

Endpoints:
  GET    /api/merchant-subscriptions/plans
  POST   /api/merchant-subscriptions/plans
  PATCH  /api/merchant-subscriptions/plans/{id}
  DELETE /api/merchant-subscriptions/plans/{id}
  GET    /api/merchant-subscriptions
  POST   /api/merchant-subscriptions
  PATCH  /api/merchant-subscriptions/{id}
  POST   /api/merchant-subscriptions/{id}/pause
  POST   /api/merchant-subscriptions/{id}/resume
  POST   /api/merchant-subscriptions/{id}/cancel
  GET    /api/merchant-subscriptions/analytics
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.merchant_subscriptions import MerchantSubscription, MerchantSubscriptionPlan
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/merchant-subscriptions", tags=["merchant_subscriptions"], dependencies=[Depends(require_module("crm"))])
logger = logging.getLogger(__name__)

VALID_INTERVALS = {"weekly", "monthly", "annual"}
VALID_STATUSES = {"active", "paused", "cancelled", "trialing", "past_due"}


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Schemas ───────────────────────────────────────────────────────────────────

class PlanCreateIn(BaseModel):
    name: str
    description: Optional[str] = None
    price: Decimal
    currency: str = "SEK"
    interval: str = "monthly"
    interval_count: int = 1
    trial_days: int = 0
    stripe_price_id: Optional[str] = None


class PlanUpdateIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    currency: Optional[str] = None
    interval: Optional[str] = None
    interval_count: Optional[int] = None
    trial_days: Optional[int] = None
    stripe_price_id: Optional[str] = None
    is_active: Optional[bool] = None


class PlanOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    price: str
    currency: str
    interval: str
    interval_count: int
    trial_days: int
    stripe_price_id: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str


class SubscriptionCreateIn(BaseModel):
    plan_id: str
    customer_id: str
    start_date: Optional[date] = None


class SubscriptionUpdateIn(BaseModel):
    plan_id: Optional[str] = None
    proration_amount: Optional[Decimal] = None
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None


class CancelIn(BaseModel):
    notice_period_days: int = 30


class SubscriptionOut(BaseModel):
    id: str
    plan_id: str
    customer_id: str
    status: str
    stripe_subscription_id: Optional[str]
    stripe_customer_id: Optional[str]
    trial_end: Optional[str]
    current_period_start: Optional[str]
    current_period_end: Optional[str]
    cancel_at: Optional[str]
    cancelled_at: Optional[str]
    paused_at: Optional[str]
    resume_at: Optional[str]
    notice_period_days: int
    proration_amount: Optional[str]
    created_at: str
    updated_at: str


def _plan_out(p: MerchantSubscriptionPlan) -> PlanOut:
    return PlanOut(
        id=str(p.id),
        name=p.name,
        description=p.description,
        price=str(p.price),
        currency=p.currency,
        interval=p.interval,
        interval_count=p.interval_count,
        trial_days=p.trial_days,
        stripe_price_id=p.stripe_price_id,
        is_active=p.is_active,
        created_at=p.created_at.isoformat(),
        updated_at=p.updated_at.isoformat(),
    )


def _sub_out(s: MerchantSubscription) -> SubscriptionOut:
    def _dt(v: Optional[datetime]) -> Optional[str]:
        return v.isoformat() if v else None

    return SubscriptionOut(
        id=str(s.id),
        plan_id=str(s.plan_id),
        customer_id=str(s.customer_id),
        status=s.status,
        stripe_subscription_id=s.stripe_subscription_id,
        stripe_customer_id=s.stripe_customer_id,
        trial_end=_dt(s.trial_end),
        current_period_start=_dt(s.current_period_start),
        current_period_end=_dt(s.current_period_end),
        cancel_at=_dt(s.cancel_at),
        cancelled_at=_dt(s.cancelled_at),
        paused_at=_dt(s.paused_at),
        resume_at=_dt(s.resume_at),
        notice_period_days=s.notice_period_days,
        proration_amount=str(s.proration_amount) if s.proration_amount is not None else None,
        created_at=s.created_at.isoformat(),
        updated_at=s.updated_at.isoformat(),
    )


def _monthly_equivalent(plan: MerchantSubscriptionPlan) -> Decimal:
    """Convert plan price to monthly-equivalent amount for MRR calculation."""
    price = plan.price
    interval = plan.interval
    count = plan.interval_count or 1
    if interval == "weekly":
        # 4.33 weeks per month
        return price * Decimal("4.333333") / Decimal(count)
    if interval == "annual":
        return price / Decimal(12 * count)
    # monthly (default)
    return price / Decimal(count)


# ── Plan Endpoints ─────────────────────────────────────────────────────────────

@router.get("/plans", response_model=list[PlanOut])
async def list_plans(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """List all billing plans for this org."""
    org_id = _org(ctx)
    try:
        rows = await db.execute(
            select(MerchantSubscriptionPlan)
            .where(MerchantSubscriptionPlan.org_id == org_id)
            .order_by(MerchantSubscriptionPlan.created_at.desc())
        )
        return [_plan_out(p) for p in rows.scalars()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "merchant_subs_list_plans failed: %s", str(e), extra={"org_id": str(org_id)}
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/plans", response_model=PlanOut, status_code=201)
async def create_plan(
    body: PlanCreateIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Create a new billing plan."""
    org_id = _org(ctx)
    if body.interval not in VALID_INTERVALS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid interval '{body.interval}'. Valid: {sorted(VALID_INTERVALS)}",
        )
    try:
        plan = MerchantSubscriptionPlan(
            org_id=org_id,
            name=body.name,
            description=body.description,
            price=body.price,
            currency=body.currency,
            interval=body.interval,
            interval_count=body.interval_count,
            trial_days=body.trial_days,
            stripe_price_id=body.stripe_price_id,
            is_active=True,
        )
        db.add(plan)
        await db.commit()
        await db.refresh(plan)
        return _plan_out(plan)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "merchant_subs_create_plan failed: %s", str(e), extra={"org_id": str(org_id)}
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/plans/{plan_id}", response_model=PlanOut)
async def update_plan(
    plan_id: uuid.UUID,
    body: PlanUpdateIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing billing plan."""
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(MerchantSubscriptionPlan).where(
                MerchantSubscriptionPlan.id == plan_id,
                MerchantSubscriptionPlan.org_id == org_id,
            )
        )
        plan = row.scalar_one_or_none()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        if body.name is not None:
            plan.name = body.name
        if body.description is not None:
            plan.description = body.description
        if body.price is not None:
            plan.price = body.price
        if body.currency is not None:
            plan.currency = body.currency
        if body.interval is not None:
            if body.interval not in VALID_INTERVALS:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid interval. Valid: {sorted(VALID_INTERVALS)}",
                )
            plan.interval = body.interval
        if body.interval_count is not None:
            plan.interval_count = body.interval_count
        if body.trial_days is not None:
            plan.trial_days = body.trial_days
        if body.stripe_price_id is not None:
            plan.stripe_price_id = body.stripe_price_id
        if body.is_active is not None:
            plan.is_active = body.is_active

        plan.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(plan)
        return _plan_out(plan)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "merchant_subs_update_plan failed: %s", str(e), extra={"org_id": str(org_id)}
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/plans/{plan_id}", status_code=204)
async def deactivate_plan(
    plan_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a plan (soft delete — sets is_active=false)."""
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(MerchantSubscriptionPlan).where(
                MerchantSubscriptionPlan.id == plan_id,
                MerchantSubscriptionPlan.org_id == org_id,
            )
        )
        plan = row.scalar_one_or_none()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        plan.is_active = False
        plan.updated_at = datetime.now(timezone.utc)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "merchant_subs_deactivate_plan failed: %s", str(e), extra={"org_id": str(org_id)}
        )
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Subscription Endpoints ────────────────────────────────────────────────────

@router.get("/analytics")
async def get_analytics(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return MRR, churn rate, new subscriptions count, and active count."""
    org_id = _org(ctx)
    try:
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)

        # Active subscriptions with their plans for MRR
        active_rows = await db.execute(
            select(MerchantSubscription, MerchantSubscriptionPlan)
            .join(
                MerchantSubscriptionPlan,
                MerchantSubscription.plan_id == MerchantSubscriptionPlan.id,
            )
            .where(
                MerchantSubscription.org_id == org_id,
                MerchantSubscription.status == "active",
            )
        )
        active_pairs = list(active_rows)
        active_count = len(active_pairs)

        mrr = sum(_monthly_equivalent(plan) for _, plan in active_pairs)

        # Subscriptions cancelled in last 30 days
        cancelled_row = await db.execute(
            select(func.count(MerchantSubscription.id)).where(
                MerchantSubscription.org_id == org_id,
                MerchantSubscription.cancelled_at >= thirty_days_ago,
            )
        )
        cancelled_count = cancelled_row.scalar_one() or 0

        # Total subs for churn denominator
        total_row = await db.execute(
            select(func.count(MerchantSubscription.id)).where(
                MerchantSubscription.org_id == org_id,
            )
        )
        total_count = total_row.scalar_one() or 0

        churn_rate = (
            round(cancelled_count / total_count * 100, 2) if total_count > 0 else 0.0
        )

        # New subscriptions in last 30 days
        new_row = await db.execute(
            select(func.count(MerchantSubscription.id)).where(
                MerchantSubscription.org_id == org_id,
                MerchantSubscription.created_at >= thirty_days_ago,
            )
        )
        new_count = new_row.scalar_one() or 0

        return {
            "mrr": str(round(mrr, 2)),
            "churn_rate": churn_rate,
            "new_count": new_count,
            "active_count": active_count,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "merchant_subs_analytics failed: %s", str(e), extra={"org_id": str(org_id)}
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=dict)
async def list_subscriptions(
    status: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    plan_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """List subscriptions with optional filters by status, customer, or plan."""
    org_id = _org(ctx)
    try:
        q = select(MerchantSubscription).where(MerchantSubscription.org_id == org_id)
        if status:
            q = q.where(MerchantSubscription.status == status)
        if customer_id:
            q = q.where(MerchantSubscription.customer_id == uuid.UUID(customer_id))
        if plan_id:
            q = q.where(MerchantSubscription.plan_id == uuid.UUID(plan_id))

        rows = await db.execute(
            q.order_by(MerchantSubscription.created_at.desc())
            .limit(limit)
            .offset((page - 1) * limit)
        )
        subs = [_sub_out(s) for s in rows.scalars()]
        return {"subscriptions": subs, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "merchant_subs_list failed: %s", str(e), extra={"org_id": str(org_id)}
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=SubscriptionOut, status_code=201)
async def create_subscription(
    body: SubscriptionCreateIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Create a subscription for a customer to a plan."""
    org_id = _org(ctx)
    try:
        plan_id = uuid.UUID(body.plan_id)
        customer_id = uuid.UUID(body.customer_id)

        # Verify plan belongs to org and is active
        plan_row = await db.execute(
            select(MerchantSubscriptionPlan).where(
                MerchantSubscriptionPlan.id == plan_id,
                MerchantSubscriptionPlan.org_id == org_id,
                MerchantSubscriptionPlan.is_active.is_(True),
            )
        )
        plan = plan_row.scalar_one_or_none()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found or inactive")

        start = datetime.combine(
            body.start_date or date.today(), datetime.min.time(), tzinfo=timezone.utc
        )

        sub = MerchantSubscription(
            org_id=org_id,
            plan_id=plan_id,
            customer_id=customer_id,
            status="active",
            current_period_start=start,
        )
        db.add(sub)
        await db.commit()
        await db.refresh(sub)
        return _sub_out(sub)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "merchant_subs_create failed: %s", str(e), extra={"org_id": str(org_id)}
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{sub_id}", response_model=SubscriptionOut)
async def update_subscription(
    sub_id: uuid.UUID,
    body: SubscriptionUpdateIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Update a subscription (e.g. plan upgrade/downgrade with proration)."""
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(MerchantSubscription).where(
                MerchantSubscription.id == sub_id,
                MerchantSubscription.org_id == org_id,
            )
        )
        sub = row.scalar_one_or_none()
        if not sub:
            raise HTTPException(status_code=404, detail="Subscription not found")

        if body.plan_id is not None:
            new_plan_id = uuid.UUID(body.plan_id)
            plan_row = await db.execute(
                select(MerchantSubscriptionPlan).where(
                    MerchantSubscriptionPlan.id == new_plan_id,
                    MerchantSubscriptionPlan.org_id == org_id,
                    MerchantSubscriptionPlan.is_active.is_(True),
                )
            )
            if not plan_row.scalar_one_or_none():
                raise HTTPException(status_code=404, detail="Target plan not found or inactive")
            sub.plan_id = new_plan_id

        if body.proration_amount is not None:
            sub.proration_amount = body.proration_amount
        if body.stripe_subscription_id is not None:
            sub.stripe_subscription_id = body.stripe_subscription_id
        if body.stripe_customer_id is not None:
            sub.stripe_customer_id = body.stripe_customer_id

        sub.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(sub)
        return _sub_out(sub)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "merchant_subs_update failed: %s", str(e), extra={"org_id": str(org_id)}
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{sub_id}/pause", response_model=SubscriptionOut)
async def pause_subscription(
    sub_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Pause an active subscription."""
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(MerchantSubscription).where(
                MerchantSubscription.id == sub_id,
                MerchantSubscription.org_id == org_id,
            )
        )
        sub = row.scalar_one_or_none()
        if not sub:
            raise HTTPException(status_code=404, detail="Subscription not found")
        if sub.status != "active":
            raise HTTPException(
                status_code=422,
                detail=f"Cannot pause subscription with status '{sub.status}'",
            )
        now = datetime.now(timezone.utc)
        sub.status = "paused"
        sub.paused_at = now
        sub.updated_at = now
        await db.commit()
        await db.refresh(sub)
        return _sub_out(sub)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "merchant_subs_pause failed: %s", str(e), extra={"org_id": str(org_id)}
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{sub_id}/resume", response_model=SubscriptionOut)
async def resume_subscription(
    sub_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Resume a paused subscription."""
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(MerchantSubscription).where(
                MerchantSubscription.id == sub_id,
                MerchantSubscription.org_id == org_id,
            )
        )
        sub = row.scalar_one_or_none()
        if not sub:
            raise HTTPException(status_code=404, detail="Subscription not found")
        if sub.status != "paused":
            raise HTTPException(
                status_code=422,
                detail=f"Cannot resume subscription with status '{sub.status}'",
            )
        now = datetime.now(timezone.utc)
        sub.status = "active"
        sub.resume_at = now
        sub.updated_at = now
        await db.commit()
        await db.refresh(sub)
        return _sub_out(sub)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "merchant_subs_resume failed: %s", str(e), extra={"org_id": str(org_id)}
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{sub_id}/cancel", response_model=SubscriptionOut)
async def cancel_subscription(
    sub_id: uuid.UUID,
    body: CancelIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Schedule a subscription for cancellation after the notice period."""
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(MerchantSubscription).where(
                MerchantSubscription.id == sub_id,
                MerchantSubscription.org_id == org_id,
            )
        )
        sub = row.scalar_one_or_none()
        if not sub:
            raise HTTPException(status_code=404, detail="Subscription not found")
        if sub.status == "cancelled":
            raise HTTPException(status_code=422, detail="Subscription is already cancelled")

        now = datetime.now(timezone.utc)
        sub.cancel_at = now + timedelta(days=body.notice_period_days)
        sub.notice_period_days = body.notice_period_days
        sub.updated_at = now
        # Status remains active until cancel_at — do not immediately set to cancelled
        await db.commit()
        await db.refresh(sub)
        return _sub_out(sub)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "merchant_subs_cancel failed: %s", str(e), extra={"org_id": str(org_id)}
        )
        raise HTTPException(status_code=500, detail="Internal server error")
