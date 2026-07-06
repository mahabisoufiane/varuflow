"""Watch sessions router — Sprint 15.  prefix /api/watch-sessions"""
from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.features.mobile.watch_session import WatchSession
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/watch-sessions", tags=["watch-sessions"], dependencies=[Depends(require_module("analytics"))])

SESSION_TTL_DAYS = 30


def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.user_id


# ── Schemas ────────────────────────────────────────────────────────────────────

class WatchSessionOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    user_id: uuid.UUID
    platform: str
    device_id: str
    paired_at: datetime
    expires_at: datetime
    last_used_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WatchSessionCreatedOut(WatchSessionOut):
    session_token: str  # plaintext — only returned once


class PairWatchIn(BaseModel):
    device_id: str
    platform: str  # apple_watch / wear_os


class TodayBookingOut(BaseModel):
    id: uuid.UUID
    customer_name: Optional[str]
    start_time: Optional[datetime]
    status: Optional[str]


class CompleteBookingIn(BaseModel):
    pass  # no body needed


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[WatchSessionOut])
async def list_watch_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        q = (
            select(WatchSession)
            .where(
                WatchSession.org_id == org_id,
                WatchSession.user_id == user_id,
                WatchSession.is_active.is_(True),
            )
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(q)
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_watch_sessions failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/", response_model=WatchSessionCreatedOut, status_code=201)
async def pair_watch(
    body: PairWatchIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        now = datetime.now(timezone.utc)
        plaintext_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(plaintext_token.encode()).hexdigest()
        expires_at = now + timedelta(days=SESSION_TTL_DAYS)

        stmt = (
            pg_insert(WatchSession)
            .values(
                org_id=org_id,
                user_id=user_id,
                platform=body.platform,
                device_id=body.device_id,
                session_token_hash=token_hash,
                paired_at=now,
                expires_at=expires_at,
                is_active=True,
            )
            .on_conflict_do_update(
                constraint="uq_watch_sessions_org_user_device",
                set_={
                    "platform": body.platform,
                    "session_token_hash": token_hash,
                    "paired_at": now,
                    "expires_at": expires_at,
                    "is_active": True,
                },
            )
            .returning(WatchSession)
        )
        result = await db.execute(stmt)
        await db.commit()
        session = result.scalar_one()
        out = WatchSessionCreatedOut.model_validate(session)
        out.session_token = plaintext_token
        return out
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"pair_watch failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{session_id}", status_code=204)
async def revoke_watch_session(
    session_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        session = await db.get(WatchSession, session_id)
        if not session or session.org_id != org_id or session.user_id != user_id:
            raise HTTPException(status_code=404, detail="Watch session not found")
        session.is_active = False
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"revoke_watch_session failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{session_id}/refresh", response_model=WatchSessionOut)
async def refresh_watch_session(
    session_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        session = await db.get(WatchSession, session_id)
        if not session or session.org_id != org_id or session.user_id != user_id:
            raise HTTPException(status_code=404, detail="Watch session not found")
        session.expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)
        await db.commit()
        await db.refresh(session)
        return session
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"refresh_watch_session failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/today", response_model=list[TodayBookingOut])
async def get_today_bookings(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        rows = await db.execute(
            text(
                "SELECT b.id, c.company_name AS customer_name, b.start_time, b.status "
                "FROM appointments b "
                "LEFT JOIN customers c ON c.id = b.customer_id "
                "WHERE b.org_id = :org_id "
                "AND b.start_time >= :start "
                                "ORDER BY b.start_time ASC "
                "LIMIT 50"
            ),
            {"org_id": str(org_id), "start": today_start},
        )
        return [
            TodayBookingOut(
                id=row.id,
                customer_name=row.customer_name,
                start_time=row.start_time,
                status=row.status,
            )
            for row in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_today_bookings failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/bookings/{booking_id}/complete", status_code=200)
async def complete_booking(
    booking_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        result = await db.execute(
            text(
                "UPDATE bookings SET status = 'completed', updated_at = NOW() "
                "WHERE id = :id AND org_id = :org_id AND deleted_at IS NULL "
                "RETURNING id"
            ),
            {"id": str(booking_id), "org_id": str(org_id)},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Booking not found")
        await db.commit()
        return {"id": str(booking_id), "status": "completed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"complete_booking failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
