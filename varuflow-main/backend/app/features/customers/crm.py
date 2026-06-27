"""CRM router: pipeline, deals, activities, forecast, analytics, custom stages."""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from .models import Deal, DealActivity, DealStage

log = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_module("crm"))])

# Built-in stages — used when an org has no custom stages configured.
# slug → {label, color, probability, is_won, is_lost}
BUILTIN_STAGES: list[dict] = [
    {"slug": "lead",          "name": "Lead",          "color": "bg-gray-200",   "probability": 10,  "is_won": False, "is_lost": False, "order_idx": 0},
    {"slug": "qualified",     "name": "Qualified",     "color": "bg-blue-200",   "probability": 25,  "is_won": False, "is_lost": False, "order_idx": 1},
    {"slug": "proposal_sent", "name": "Proposal Sent", "color": "bg-yellow-200", "probability": 50,  "is_won": False, "is_lost": False, "order_idx": 2},
    {"slug": "negotiation",   "name": "Negotiation",   "color": "bg-orange-200", "probability": 75,  "is_won": False, "is_lost": False, "order_idx": 3},
    {"slug": "won",           "name": "Won",           "color": "bg-green-300",  "probability": 100, "is_won": True,  "is_lost": False, "order_idx": 4},
    {"slug": "lost",          "name": "Lost",          "color": "bg-red-200",    "probability": 0,   "is_won": False, "is_lost": True,  "order_idx": 5},
    # Legacy aliases so old data keeps working
    {"slug": "prospect",      "name": "Lead",          "color": "bg-gray-200",   "probability": 10,  "is_won": False, "is_lost": False, "order_idx": 0},
    {"slug": "proposal",      "name": "Proposal Sent", "color": "bg-yellow-200", "probability": 50,  "is_won": False, "is_lost": False, "order_idx": 2},
]
BUILTIN_SLUGS = {s["slug"] for s in BUILTIN_STAGES}

# Active canonical stages for board rendering (no legacy aliases)
CANONICAL_STAGES = [s for s in BUILTIN_STAGES if s["slug"] not in ("prospect", "proposal")]

VALID_ACTIVITY_TYPES = {"call", "meeting", "email", "note", "stage_change"}

# Stage-weight fallback for forecast
_STAGE_PROB = {s["slug"]: s["probability"] / 100.0 for s in BUILTIN_STAGES}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _is_closed(stage: str) -> bool:
    info = next((s for s in BUILTIN_STAGES if s["slug"] == stage), None)
    return bool(info and (info["is_won"] or info["is_lost"]))

def _is_won(stage: str) -> bool:
    info = next((s for s in BUILTIN_STAGES if s["slug"] == stage), None)
    return bool(info and info["is_won"])


async def _get_stages(db: AsyncSession, org_id: uuid.UUID) -> list[dict]:
    """Return the org's custom stages sorted by order_idx, or CANONICAL_STAGES."""
    rows = (await db.execute(
        select(DealStage).where(DealStage.org_id == org_id).order_by(DealStage.order_idx)
    )).scalars().all()
    if rows:
        return [{"slug": r.slug, "name": r.name, "color": r.color or "bg-gray-200",
                 "probability": 50, "is_won": r.is_won, "is_lost": r.is_lost,
                 "order_idx": r.order_idx} for r in rows]
    return CANONICAL_STAGES


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class DealCreate(BaseModel):
    title: str
    stage: str = "lead"
    value: Optional[float] = None
    currency: str = "SEK"
    close_date: Optional[date] = None
    customer_id: Optional[uuid.UUID] = None
    owner_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    probability: Optional[int] = None
    quote_id: Optional[uuid.UUID] = None


class DealUpdate(BaseModel):
    title: Optional[str] = None
    stage: Optional[str] = None
    value: Optional[float] = None
    currency: Optional[str] = None
    close_date: Optional[date] = None
    customer_id: Optional[uuid.UUID] = None
    owner_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    probability: Optional[int] = None
    quote_id: Optional[uuid.UUID] = None
    invoice_id: Optional[uuid.UUID] = None
    win_reason: Optional[str] = None
    loss_reason: Optional[str] = None


class ActivityCreate(BaseModel):
    activity_type: str
    note: Optional[str] = None
    actor_name: Optional[str] = None


class StageCreate(BaseModel):
    name: str
    slug: str
    color: Optional[str] = None
    order_idx: int = 0
    is_won: bool = False
    is_lost: bool = False


class StagePatch(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    order_idx: Optional[int] = None
    is_won: Optional[bool] = None
    is_lost: Optional[bool] = None


# ── Serializers ──────────────────────────────────────────────────────────────

def _activity_out(a: DealActivity) -> dict:
    return {
        "id": str(a.id),
        "deal_id": str(a.deal_id),
        "activity_type": a.activity_type,
        "note": a.note,
        "actor_name": a.actor_name,
        "old_value": a.old_value,
        "new_value": a.new_value,
        "created_at": a.created_at.isoformat(),
    }


def _deal_out(d: Deal, include_activities: bool = False) -> dict:
    # Sales cycle days: from created_at to closed_at (or today for open deals)
    closed = d.closed_at or (datetime.now(timezone.utc) if _is_closed(d.stage) else None)
    sales_cycle_days: Optional[int] = None
    if closed and d.created_at:
        sales_cycle_days = max(0, (closed.replace(tzinfo=timezone.utc) - d.created_at.replace(tzinfo=timezone.utc)).days)

    out: dict[str, Any] = {
        "id": str(d.id),
        "title": d.title,
        "stage": d.stage,
        "value": float(d.value) if d.value is not None else None,
        "currency": d.currency,
        "close_date": d.close_date.isoformat() if d.close_date else None,
        "customer_id": str(d.customer_id) if d.customer_id else None,
        "owner_id": str(d.owner_id) if d.owner_id else None,
        "notes": d.notes,
        "probability": d.probability,
        "win_reason": d.win_reason,
        "loss_reason": d.loss_reason,
        "closed_at": d.closed_at.isoformat() if d.closed_at else None,
        "quote_id": str(d.quote_id) if d.quote_id else None,
        "invoice_id": str(d.invoice_id) if d.invoice_id else None,
        "sales_cycle_days": sales_cycle_days,
        "created_at": d.created_at.isoformat(),
        "updated_at": d.updated_at.isoformat(),
    }
    if include_activities:
        out["activities"] = [_activity_out(a) for a in d.activities]
    return out


# ── Pipeline board ───────────────────────────────────────────────────────────

@router.get("/api/crm/pipeline")
async def get_pipeline(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        stages = await _get_stages(db, org_id)
        result = await db.execute(
            select(Deal).where(Deal.org_id == org_id).order_by(Deal.created_at.desc())
        )
        deals = result.scalars().all()
        pipeline: dict[str, dict] = {
            s["slug"]: {"stage": s, "deals": [], "total_value": 0.0}
            for s in stages
        }
        # Include deal in its stage bucket; if stage not in current config, still include
        for d in deals:
            if d.stage not in pipeline:
                pipeline[d.stage] = {"stage": {"slug": d.stage, "name": d.stage, "color": "bg-gray-100"}, "deals": [], "total_value": 0.0}
            pipeline[d.stage]["deals"].append(_deal_out(d))
            pipeline[d.stage]["total_value"] += float(d.value or 0)
        return {"stages": stages, "pipeline": pipeline}
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_pipeline failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Deals CRUD ───────────────────────────────────────────────────────────────

@router.get("/api/crm/deals")
async def list_deals(
    stage: Optional[str] = None,
    customer_id: Optional[str] = None,
    owner_id: Optional[str] = None,
    is_closed: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        q = select(Deal).where(Deal.org_id == org_id)
        if stage:
            q = q.where(Deal.stage == stage)
        if customer_id:
            q = q.where(Deal.customer_id == uuid.UUID(customer_id))
        if owner_id:
            q = q.where(Deal.owner_id == uuid.UUID(owner_id))
        if is_closed is True:
            q = q.where(Deal.closed_at.isnot(None))
        elif is_closed is False:
            q = q.where(Deal.closed_at.is_(None))
        if search:
            q = q.where(Deal.title.ilike(f"%{search}%"))
        q = q.order_by(Deal.created_at.desc()).limit(limit).offset(offset)
        deals = (await db.execute(q)).scalars().all()
        return [_deal_out(d) for d in deals]
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_deals failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/crm/deals", status_code=201)
async def create_deal(
    body: DealCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        stages = await _get_stages(db, org_id)
        valid_slugs = {s["slug"] for s in stages} | BUILTIN_SLUGS
        if body.stage not in valid_slugs:
            raise HTTPException(status_code=422, detail=f"Invalid stage: {body.stage}")
        deal = Deal(
            id=uuid.uuid4(),
            org_id=org_id,
            title=body.title,
            stage=body.stage,
            value=Decimal(str(body.value)) if body.value is not None else None,
            currency=body.currency,
            close_date=body.close_date,
            customer_id=body.customer_id,
            owner_id=body.owner_id,
            notes=body.notes,
            probability=body.probability,
            quote_id=body.quote_id,
        )
        db.add(deal)
        await db.commit()
        await db.refresh(deal)
        return _deal_out(deal)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_deal failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/crm/deals/{deal_id}")
async def get_deal(
    deal_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        result = await db.execute(
            select(Deal)
            .where(and_(Deal.id == deal_id, Deal.org_id == org_id))
            .options(selectinload(Deal.activities))
        )
        deal = result.scalars().first()
        if not deal:
            raise HTTPException(status_code=404, detail="Deal not found")
        return _deal_out(deal, include_activities=True)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_deal failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/crm/deals/{deal_id}")
async def update_deal(
    deal_id: uuid.UUID,
    body: DealUpdate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        result = await db.execute(
            select(Deal)
            .where(and_(Deal.id == deal_id, Deal.org_id == org_id))
            .options(selectinload(Deal.activities))
        )
        deal = result.scalars().first()
        if not deal:
            raise HTTPException(status_code=404, detail="Deal not found")

        old_stage = deal.stage
        if body.title is not None:
            deal.title = body.title
        if body.stage is not None:
            stages = await _get_stages(db, org_id)
            valid_slugs = {s["slug"] for s in stages} | BUILTIN_SLUGS
            if body.stage not in valid_slugs:
                raise HTTPException(status_code=422, detail=f"Invalid stage: {body.stage}")
            deal.stage = body.stage
        if body.value is not None:
            deal.value = Decimal(str(body.value))
        if body.currency is not None:
            deal.currency = body.currency
        if body.close_date is not None:
            deal.close_date = body.close_date
        if body.customer_id is not None:
            deal.customer_id = body.customer_id
        if body.owner_id is not None:
            deal.owner_id = body.owner_id
        if body.notes is not None:
            deal.notes = body.notes
        if body.probability is not None:
            deal.probability = body.probability
        if body.quote_id is not None:
            deal.quote_id = body.quote_id
        if body.invoice_id is not None:
            deal.invoice_id = body.invoice_id
        if body.win_reason is not None:
            deal.win_reason = body.win_reason
        if body.loss_reason is not None:
            deal.loss_reason = body.loss_reason

        # Handle stage change
        if body.stage and body.stage != old_stage:
            now = datetime.now(timezone.utc)
            # Set closed_at when entering a terminal stage
            if _is_closed(body.stage) and not deal.closed_at:
                deal.closed_at = now
            # Clear closed_at if reopened
            elif not _is_closed(body.stage) and deal.closed_at:
                deal.closed_at = None

            db.add(DealActivity(
                id=uuid.uuid4(), org_id=org_id, deal_id=deal_id,
                activity_type="stage_change",
                old_value=old_stage, new_value=body.stage,
            ))
            if deal.customer_id:
                await _trigger_deal_stage_sequences(db, org_id, deal, body.stage)

        await db.commit()
        await db.refresh(deal)
        return _deal_out(deal, include_activities=True)
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_deal failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/crm/deals/{deal_id}", status_code=204)
async def delete_deal(
    deal_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        result = await db.execute(
            select(Deal).where(and_(Deal.id == deal_id, Deal.org_id == org_id))
        )
        deal = result.scalars().first()
        if not deal:
            raise HTTPException(status_code=404, detail="Deal not found")
        await db.delete(deal)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_deal failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Activities ────────────────────────────────────────────────────────────────

@router.post("/api/crm/deals/{deal_id}/activities", status_code=201)
async def log_activity(
    deal_id: uuid.UUID,
    body: ActivityCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        if body.activity_type not in VALID_ACTIVITY_TYPES:
            raise HTTPException(status_code=422, detail=f"Invalid activity_type: {body.activity_type}")
        result = await db.execute(
            select(Deal).where(and_(Deal.id == deal_id, Deal.org_id == org_id))
        )
        if not result.scalars().first():
            raise HTTPException(status_code=404, detail="Deal not found")
        activity = DealActivity(
            id=uuid.uuid4(), org_id=org_id, deal_id=deal_id,
            activity_type=body.activity_type, note=body.note, actor_name=body.actor_name,
        )
        db.add(activity)
        await db.commit()
        await db.refresh(activity)
        return _activity_out(activity)
    except HTTPException:
        raise
    except Exception as e:
        log.error("log_activity failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Custom stages ─────────────────────────────────────────────────────────────

@router.get("/api/crm/stages")
async def get_stages(ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = ctx[1]
        return await _get_stages(db, org_id)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_stages failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/crm/stages", status_code=201)
async def create_stage(body: StageCreate, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = ctx[1]
        stage = DealStage(org_id=org_id, name=body.name, slug=body.slug,
                          color=body.color, order_idx=body.order_idx,
                          is_won=body.is_won, is_lost=body.is_lost)
        db.add(stage)
        await db.commit()
        await db.refresh(stage)
        return {"id": str(stage.id), "slug": stage.slug, "name": stage.name,
                "color": stage.color, "order_idx": stage.order_idx,
                "is_won": stage.is_won, "is_lost": stage.is_lost}
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_stage failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/crm/stages/{stage_id}")
async def update_stage(stage_id: uuid.UUID, body: StagePatch, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = ctx[1]
        stage = (await db.execute(select(DealStage).where(DealStage.id == stage_id, DealStage.org_id == org_id))).scalar_one_or_none()
        if not stage:
            raise HTTPException(status_code=404, detail="Stage not found")
        if body.name is not None: stage.name = body.name
        if body.color is not None: stage.color = body.color
        if body.order_idx is not None: stage.order_idx = body.order_idx
        if body.is_won is not None: stage.is_won = body.is_won
        if body.is_lost is not None: stage.is_lost = body.is_lost
        await db.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_stage failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/crm/stages/{stage_id}", status_code=204)
async def delete_stage(stage_id: uuid.UUID, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = ctx[1]
        stage = (await db.execute(select(DealStage).where(DealStage.id == stage_id, DealStage.org_id == org_id))).scalar_one_or_none()
        if not stage:
            raise HTTPException(status_code=404, detail="Stage not found")
        await db.delete(stage)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_stage failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Forecast ──────────────────────────────────────────────────────────────────

@router.get("/api/crm/forecast")
async def get_forecast(
    months: int = 3,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        if months < 1 or months > 24:
            months = 3
        result = await db.execute(
            select(Deal).where(
                and_(
                    Deal.org_id == org_id,
                    Deal.stage.notin_(["won", "lost"]),
                    Deal.close_date.isnot(None),
                )
            )
        )
        deals = result.scalars().all()

        from collections import defaultdict
        monthly: dict[str, dict] = defaultdict(lambda: {
            "deals": 0, "total_value": 0.0, "weighted_value": 0.0, "by_stage": {}
        })

        for d in deals:
            if d.close_date is None or d.value is None:
                continue
            month_key = d.close_date.strftime("%Y-%m")
            val = float(d.value)
            prob = (d.probability / 100.0) if d.probability is not None else _STAGE_PROB.get(d.stage, 0.1)
            monthly[month_key]["deals"] += 1
            monthly[month_key]["total_value"] += val
            monthly[month_key]["weighted_value"] += val * prob
            by_stage = monthly[month_key]["by_stage"]
            by_stage[d.stage] = by_stage.get(d.stage, 0.0) + val

        return {
            "months": dict(sorted(monthly.items())[:months]),
            "total_pipeline": sum(float(d.value) for d in deals if d.value),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_forecast failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Analytics ─────────────────────────────────────────────────────────────────

@router.get("/api/crm/analytics")
async def get_crm_analytics(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Win rate, avg sales cycle, revenue won vs lost, win/loss reason breakdown."""
    try:
        org_id = ctx[1]
        rows = (await db.execute(
            select(Deal).where(Deal.org_id == org_id)
        )).scalars().all()

        total = len(rows)
        won = [d for d in rows if _is_won(d.stage)]
        lost = [d for d in rows if d.stage == "lost"]
        open_ = [d for d in rows if not _is_closed(d.stage)]

        win_rate = round(len(won) / (len(won) + len(lost)) * 100, 1) if (won or lost) else 0.0

        # Avg sales cycle for closed deals with closed_at
        cycle_days = [
            (d.closed_at - d.created_at).days
            for d in won + lost
            if d.closed_at and d.created_at
        ]
        avg_cycle = round(sum(cycle_days) / len(cycle_days), 1) if cycle_days else None

        won_revenue = float(sum(d.value or 0 for d in won))
        lost_revenue = float(sum(d.value or 0 for d in lost))
        pipeline_value = float(sum(d.value or 0 for d in open_))

        # Win/loss reason frequency
        win_reasons: dict[str, int] = {}
        for d in won:
            if d.win_reason:
                win_reasons[d.win_reason] = win_reasons.get(d.win_reason, 0) + 1
        loss_reasons: dict[str, int] = {}
        for d in lost:
            if d.loss_reason:
                loss_reasons[d.loss_reason] = loss_reasons.get(d.loss_reason, 0) + 1

        # Stage breakdown
        stage_count: dict[str, int] = {}
        for d in rows:
            stage_count[d.stage] = stage_count.get(d.stage, 0) + 1

        return {
            "total_deals": total,
            "win_rate_pct": win_rate,
            "avg_sales_cycle_days": avg_cycle,
            "won_revenue": won_revenue,
            "lost_revenue": lost_revenue,
            "pipeline_value": pipeline_value,
            "stage_breakdown": stage_count,
            "win_reasons": win_reasons,
            "loss_reasons": loss_reasons,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_crm_analytics failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Internal helper ───────────────────────────────────────────────────────────

async def _trigger_deal_stage_sequences(
    db: AsyncSession,
    org_id: uuid.UUID,
    deal: Deal,
    new_stage: str,
) -> None:
    """Enroll the deal's customer in any deal_stage sequences for the new stage."""
    from datetime import timedelta
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.features.marketing.email_sequences_models import EmailSequence, EmailSequenceEnrollment, EmailSequenceStep
    from app.features.invoicing.models import Customer

    seq_result = await db.execute(
        select(EmailSequence).where(
            and_(
                EmailSequence.org_id == org_id,
                EmailSequence.trigger_type == "deal_stage",
                EmailSequence.trigger_value == new_stage,
                EmailSequence.is_active.is_(True),
            )
        )
    )
    sequences = seq_result.scalars().all()
    if not sequences:
        return

    cust_result = await db.execute(
        select(Customer.email).where(Customer.id == deal.customer_id)
    )
    row = cust_result.first()
    if not row or not row[0]:
        return
    email = row[0]

    now = datetime.now(timezone.utc)
    for seq in sequences:
        step_result = await db.execute(
            select(EmailSequenceStep)
            .where(EmailSequenceStep.sequence_id == seq.id)
            .order_by(EmailSequenceStep.step_number)
            .limit(1)
        )
        first_step = step_result.scalars().first()
        send_at = now + timedelta(days=first_step.delay_days) if first_step else now

        stmt = (
            pg_insert(EmailSequenceEnrollment)
            .values(
                id=uuid.uuid4(),
                sequence_id=seq.id,
                org_id=org_id,
                customer_id=deal.customer_id,
                email=email,
                status="active",
                current_step=0,
                next_send_at=send_at,
                enrolled_at=now,
            )
            .on_conflict_do_nothing(constraint="uq_seq_enrollment_customer")
        )
        await db.execute(stmt)
