"""Marketing attribution — sources and events for channel-level ROI tracking.

Endpoints
─────────
GET    /api/attribution/sources         → list sources
POST   /api/attribution/sources         → create source
PATCH  /api/attribution/sources/{id}    → update source
DELETE /api/attribution/sources/{id}    → delete source
POST   /api/attribution/events          → log attribution event
GET    /api/attribution/summary         → aggregate by channel
GET    /api/attribution/funnel          → conversion funnel by channel/source
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.marketing_attribution import AttributionEvent, AttributionSource

router = APIRouter(prefix="/api/attribution", tags=["attribution"])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _source_out(s: AttributionSource) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "org_id": str(s.org_id),
        "name": s.name,
        "channel": s.channel,
        "utm_source": s.utm_source,
        "utm_medium": s.utm_medium,
        "utm_campaign": s.utm_campaign,
        "created_at": s.created_at.isoformat(),
    }


def _event_out(e: AttributionEvent) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "org_id": str(e.org_id),
        "customer_id": str(e.customer_id) if e.customer_id else None,
        "source_id": str(e.source_id) if e.source_id else None,
        "event_type": e.event_type,
        "channel": e.channel,
        "revenue": float(e.revenue) if e.revenue is not None else None,
        "occurred_at": e.occurred_at.isoformat(),
        "created_at": e.created_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class SourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    channel: str = Field(default="other", max_length=50)
    utm_source: Optional[str] = Field(default=None, max_length=200)
    utm_medium: Optional[str] = Field(default=None, max_length=200)
    utm_campaign: Optional[str] = Field(default=None, max_length=200)


class SourcePatch(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    channel: Optional[str] = Field(default=None, max_length=50)
    utm_source: Optional[str] = Field(default=None, max_length=200)
    utm_medium: Optional[str] = Field(default=None, max_length=200)
    utm_campaign: Optional[str] = Field(default=None, max_length=200)


class EventIn(BaseModel):
    source_id: Optional[uuid.UUID] = None
    customer_id: Optional[uuid.UUID] = None
    event_type: str = Field(max_length=30)
    channel: Optional[str] = Field(default=None, max_length=50)
    revenue: Optional[Decimal] = None
    occurred_at: Optional[datetime] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/sources")
async def list_sources(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        rows = (await db.execute(
            select(AttributionSource).where(AttributionSource.org_id == org_id).order_by(AttributionSource.name)
        )).scalars().all()
        return [_source_out(s) for s in rows]
    except Exception as e:
        log.error("list_sources failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sources", status_code=201)
async def create_source(
    body: SourceIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        s = AttributionSource(
            org_id=org_id,
            name=body.name,
            channel=body.channel,
            utm_source=body.utm_source,
            utm_medium=body.utm_medium,
            utm_campaign=body.utm_campaign,
        )
        db.add(s)
        await db.commit()
        await db.refresh(s)
        return _source_out(s)
    except Exception as e:
        log.error("create_source failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/sources/{source_id}")
async def patch_source(
    source_id: uuid.UUID,
    body: SourcePatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        s = await db.scalar(
            select(AttributionSource).where(AttributionSource.id == source_id, AttributionSource.org_id == org_id)
        )
        if not s:
            raise HTTPException(status_code=404, detail="Source not found")
        if body.name is not None:
            s.name = body.name
        if body.channel is not None:
            s.channel = body.channel
        if body.utm_source is not None:
            s.utm_source = body.utm_source
        if body.utm_medium is not None:
            s.utm_medium = body.utm_medium
        if body.utm_campaign is not None:
            s.utm_campaign = body.utm_campaign
        await db.commit()
        await db.refresh(s)
        return _source_out(s)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_source failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(
    source_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        s = await db.scalar(
            select(AttributionSource).where(AttributionSource.id == source_id, AttributionSource.org_id == org_id)
        )
        if not s:
            raise HTTPException(status_code=404, detail="Source not found")
        await db.delete(s)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_source failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/events", status_code=201)
async def log_event(
    body: EventIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        # Validate source belongs to org if provided
        if body.source_id:
            source = await db.scalar(
                select(AttributionSource).where(
                    AttributionSource.id == body.source_id, AttributionSource.org_id == org_id
                )
            )
            if not source:
                raise HTTPException(status_code=404, detail="Attribution source not found")

        e = AttributionEvent(
            org_id=org_id,
            source_id=body.source_id,
            customer_id=body.customer_id,
            event_type=body.event_type,
            channel=body.channel,
            revenue=body.revenue,
            occurred_at=body.occurred_at or datetime.now(timezone.utc),
        )
        db.add(e)
        await db.commit()
        await db.refresh(e)
        return _event_out(e)
    except HTTPException:
        raise
    except Exception as e:
        log.error("log_event failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/summary")
async def attribution_summary(
    from_date: Optional[str] = Query(default=None),
    to_date: Optional[str] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = select(
            AttributionEvent.channel,
            func.count(case((AttributionEvent.event_type == "lead", 1))).label("lead_count"),
            func.count(case((AttributionEvent.event_type == "conversion", 1))).label("conversion_count"),
            func.coalesce(func.sum(AttributionEvent.revenue), 0).label("total_revenue"),
            func.coalesce(func.avg(AttributionEvent.revenue), 0).label("avg_ltv"),
        ).where(AttributionEvent.org_id == org_id)

        if from_date:
            q = q.where(AttributionEvent.occurred_at >= datetime.fromisoformat(from_date))
        if to_date:
            q = q.where(AttributionEvent.occurred_at <= datetime.fromisoformat(to_date))

        q = q.group_by(AttributionEvent.channel)
        rows = (await db.execute(q)).all()

        return [
            {
                "channel": row.channel,
                "lead_count": row.lead_count,
                "conversion_count": row.conversion_count,
                "total_revenue": float(row.total_revenue),
                "avg_ltv": float(row.avg_ltv),
            }
            for row in rows
        ]
    except Exception as e:
        log.error("attribution_summary failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/funnel")
async def attribution_funnel(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = select(
            AttributionEvent.channel,
            AttributionEvent.source_id,
            func.count(case((AttributionEvent.event_type == "lead", 1))).label("leads"),
            func.count(case((AttributionEvent.event_type == "conversion", 1))).label("conversions"),
            func.count(case((AttributionEvent.event_type == "purchase", 1))).label("purchases"),
        ).where(AttributionEvent.org_id == org_id).group_by(
            AttributionEvent.channel, AttributionEvent.source_id
        )

        rows = (await db.execute(q)).all()

        return [
            {
                "channel": row.channel,
                "source_id": str(row.source_id) if row.source_id else None,
                "leads": row.leads,
                "conversions": row.conversions,
                "purchases": row.purchases,
            }
            for row in rows
        ]
    except Exception as e:
        log.error("attribution_funnel failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
