"""Voice shortcuts router — Sprint 15.  prefix /api/voice-shortcuts"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.voice_shortcut import VoiceShortcut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice-shortcuts", tags=["voice-shortcuts"])


def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.user_id


# ── Schemas ────────────────────────────────────────────────────────────────────

class ShortcutOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    user_id: uuid.UUID
    platform: str
    phrase: str
    action_type: str
    action_params: Optional[Any]
    response_template: Optional[str]
    is_active: bool
    last_triggered_at: Optional[datetime]
    trigger_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ShortcutIn(BaseModel):
    platform: str
    phrase: str
    action_type: str
    action_params: Optional[Any] = None
    response_template: Optional[str] = None


class ShortcutUpdate(BaseModel):
    platform: Optional[str] = None
    phrase: Optional[str] = None
    action_type: Optional[str] = None
    action_params: Optional[Any] = None
    response_template: Optional[str] = None
    is_active: Optional[bool] = None


class TriggerOut(BaseModel):
    shortcut_id: uuid.UUID
    response: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[ShortcutOut])
async def list_shortcuts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        q = (
            select(VoiceShortcut)
            .where(VoiceShortcut.org_id == org_id, VoiceShortcut.user_id == user_id)
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(q)
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_shortcuts failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/", response_model=ShortcutOut, status_code=201)
async def create_shortcut(
    body: ShortcutIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        shortcut = VoiceShortcut(
            org_id=org_id,
            user_id=user_id,
            platform=body.platform,
            phrase=body.phrase,
            action_type=body.action_type,
            action_params=body.action_params,
            response_template=body.response_template,
        )
        db.add(shortcut)
        await db.commit()
        await db.refresh(shortcut)
        return shortcut
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_shortcut failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{shortcut_id}", response_model=ShortcutOut)
async def update_shortcut(
    shortcut_id: uuid.UUID,
    body: ShortcutUpdate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        shortcut = await db.get(VoiceShortcut, shortcut_id)
        if not shortcut or shortcut.org_id != org_id or shortcut.user_id != user_id:
            raise HTTPException(status_code=404, detail="Voice shortcut not found")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(shortcut, field, value)
        await db.commit()
        await db.refresh(shortcut)
        return shortcut
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_shortcut failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{shortcut_id}", status_code=204)
async def delete_shortcut(
    shortcut_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        shortcut = await db.get(VoiceShortcut, shortcut_id)
        if not shortcut or shortcut.org_id != org_id or shortcut.user_id != user_id:
            raise HTTPException(status_code=404, detail="Voice shortcut not found")
        await db.delete(shortcut)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_shortcut failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{shortcut_id}/trigger", response_model=TriggerOut)
async def trigger_shortcut(
    shortcut_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        shortcut = await db.get(VoiceShortcut, shortcut_id)
        if not shortcut or shortcut.org_id != org_id or shortcut.user_id != user_id:
            raise HTTPException(status_code=404, detail="Voice shortcut not found")
        if not shortcut.is_active:
            raise HTTPException(status_code=400, detail="Voice shortcut is inactive")

        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        action = shortcut.action_type
        spoken_response: str

        if action == "today_revenue":
            row = await db.execute(
                text(
                    "SELECT COALESCE(SUM(total_amount), 0) FROM invoices "
                    "WHERE org_id = :org_id AND status = 'paid' "
                    "AND updated_at >= :start AND deleted_at IS NULL"
                ),
                {"org_id": str(org_id), "start": today_start},
            )
            amount = float(row.scalar() or 0)
            spoken_response = f"Today's revenue is {amount:.0f} SEK"

        elif action == "today_bookings":
            row = await db.execute(
                text(
                    "SELECT COUNT(*) FROM bookings "
                    "WHERE org_id = :org_id AND start_time >= :start AND deleted_at IS NULL"
                ),
                {"org_id": str(org_id), "start": today_start},
            )
            count = int(row.scalar() or 0)
            spoken_response = f"You have {count} booking{'s' if count != 1 else ''} today"

        elif action == "low_stock":
            row = await db.execute(
                text(
                    "SELECT COUNT(*) FROM stock_levels "
                    "WHERE org_id = :org_id AND quantity <= reorder_point"
                ),
                {"org_id": str(org_id)},
            )
            count = int(row.scalar() or 0)
            spoken_response = f"{count} product{'s are' if count != 1 else ' is'} running low on stock"

        elif action == "next_appointment":
            row = await db.execute(
                text(
                    "SELECT b.start_time, c.name "
                    "FROM bookings b "
                    "LEFT JOIN customers c ON c.id = b.customer_id "
                    "WHERE b.org_id = :org_id AND b.start_time >= :now "
                    "AND b.deleted_at IS NULL "
                    "ORDER BY b.start_time ASC LIMIT 1"
                ),
                {"org_id": str(org_id), "now": now},
            )
            appt = row.fetchone()
            if appt:
                customer = appt.name or "a customer"
                start_time: datetime = appt.start_time
                spoken_response = f"Your next appointment is with {customer} at {start_time.strftime('%H:%M')}"
            else:
                spoken_response = "You have no upcoming appointments"

        else:
            spoken_response = shortcut.response_template or f"Action {action} executed"

        # Update trigger stats
        shortcut.trigger_count = (shortcut.trigger_count or 0) + 1
        shortcut.last_triggered_at = now
        await db.commit()

        return TriggerOut(shortcut_id=shortcut_id, response=spoken_response)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"trigger_shortcut failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
