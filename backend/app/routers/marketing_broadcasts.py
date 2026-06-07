"""Marketing broadcasts — SMS and WhatsApp bulk messaging campaigns.

Endpoints
─────────
GET    /api/broadcasts              → list (filter: channel, status)
POST   /api/broadcasts              → create
GET    /api/broadcasts/{id}         → detail
PATCH  /api/broadcasts/{id}         → update draft
DELETE /api/broadcasts/{id}         → delete draft
POST   /api/broadcasts/{id}/send    → mark sent
POST   /api/broadcasts/{id}/schedule → set scheduled_for
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.marketing_broadcast import MarketingBroadcast

router = APIRouter(prefix="/api/broadcasts", tags=["broadcasts"], dependencies=[Depends(require_module("crm"))])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _broadcast_out(b: MarketingBroadcast) -> dict[str, Any]:
    return {
        "id": str(b.id),
        "org_id": str(b.org_id),
        "name": b.name,
        "channel": b.channel,
        "segment_id": str(b.segment_id) if b.segment_id else None,
        "body_text": b.body_text,
        "status": b.status,
        "scheduled_for": b.scheduled_for.isoformat() if b.scheduled_for else None,
        "sent_at": b.sent_at.isoformat() if b.sent_at else None,
        "recipient_count": b.recipient_count,
        "delivered_count": b.delivered_count,
        "opt_out_count": b.opt_out_count,
        "created_at": b.created_at.isoformat(),
        "updated_at": b.updated_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class BroadcastIn(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    channel: str = Field(default="sms", max_length=20)
    body_text: str = Field(min_length=1)
    segment_id: Optional[uuid.UUID] = None
    scheduled_for: Optional[datetime] = None


class BroadcastPatch(BaseModel):
    name: Optional[str] = Field(default=None, max_length=300)
    channel: Optional[str] = Field(default=None, max_length=20)
    body_text: Optional[str] = None
    segment_id: Optional[uuid.UUID] = None
    scheduled_for: Optional[datetime] = None


class ScheduleIn(BaseModel):
    scheduled_for: datetime


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_broadcasts(
    channel: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = select(MarketingBroadcast).where(MarketingBroadcast.org_id == org_id)
        if channel:
            q = q.where(MarketingBroadcast.channel == channel)
        if status:
            q = q.where(MarketingBroadcast.status == status)
        q = q.order_by(MarketingBroadcast.created_at.desc())

        rows = (await db.execute(q)).scalars().all()
        return [_broadcast_out(b) for b in rows]
    except Exception as e:
        log.error("list_broadcasts failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_broadcast(
    body: BroadcastIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        b = MarketingBroadcast(
            org_id=org_id,
            name=body.name,
            channel=body.channel,
            body_text=body.body_text,
            segment_id=body.segment_id,
            scheduled_for=body.scheduled_for,
        )
        db.add(b)
        await db.commit()
        await db.refresh(b)
        return _broadcast_out(b)
    except Exception as e:
        log.error("create_broadcast failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{broadcast_id}")
async def get_broadcast(
    broadcast_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        b = await db.scalar(
            select(MarketingBroadcast).where(MarketingBroadcast.id == broadcast_id, MarketingBroadcast.org_id == org_id)
        )
        if not b:
            raise HTTPException(status_code=404, detail="Broadcast not found")
        return _broadcast_out(b)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_broadcast failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{broadcast_id}")
async def patch_broadcast(
    broadcast_id: uuid.UUID,
    body: BroadcastPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        b = await db.scalar(
            select(MarketingBroadcast).where(MarketingBroadcast.id == broadcast_id, MarketingBroadcast.org_id == org_id)
        )
        if not b:
            raise HTTPException(status_code=404, detail="Broadcast not found")
        if b.status == "sent":
            raise HTTPException(status_code=409, detail="Cannot edit a sent broadcast")

        if body.name is not None:
            b.name = body.name
        if body.channel is not None:
            b.channel = body.channel
        if body.body_text is not None:
            b.body_text = body.body_text
        if body.segment_id is not None:
            b.segment_id = body.segment_id
        if body.scheduled_for is not None:
            b.scheduled_for = body.scheduled_for

        b.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(b)
        return _broadcast_out(b)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_broadcast failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{broadcast_id}", status_code=204)
async def delete_broadcast(
    broadcast_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        b = await db.scalar(
            select(MarketingBroadcast).where(MarketingBroadcast.id == broadcast_id, MarketingBroadcast.org_id == org_id)
        )
        if not b:
            raise HTTPException(status_code=404, detail="Broadcast not found")
        if b.status == "sent":
            raise HTTPException(status_code=409, detail="Cannot delete a sent broadcast")
        await db.delete(b)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_broadcast failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{broadcast_id}/send")
async def send_broadcast(
    broadcast_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        b = await db.scalar(
            select(MarketingBroadcast).where(MarketingBroadcast.id == broadcast_id, MarketingBroadcast.org_id == org_id)
        )
        if not b:
            raise HTTPException(status_code=404, detail="Broadcast not found")
        if b.status == "sent":
            raise HTTPException(status_code=409, detail="Broadcast already sent")

        b.status = "sent"
        b.sent_at = datetime.now(timezone.utc)
        b.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(b)
        return _broadcast_out(b)
    except HTTPException:
        raise
    except Exception as e:
        log.error("send_broadcast failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{broadcast_id}/schedule")
async def schedule_broadcast(
    broadcast_id: uuid.UUID,
    body: ScheduleIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        b = await db.scalar(
            select(MarketingBroadcast).where(MarketingBroadcast.id == broadcast_id, MarketingBroadcast.org_id == org_id)
        )
        if not b:
            raise HTTPException(status_code=404, detail="Broadcast not found")
        if b.status == "sent":
            raise HTTPException(status_code=409, detail="Cannot schedule a sent broadcast")

        b.scheduled_for = body.scheduled_for
        b.status = "scheduled"
        b.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(b)
        return _broadcast_out(b)
    except HTTPException:
        raise
    except Exception as e:
        log.error("schedule_broadcast failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
