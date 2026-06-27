"""Live Tracking — real-time staff location sharing with customers.

Endpoints
─────────
GET    /api/tracking                    → list active sessions for org
POST   /api/tracking                    → start session
GET    /api/tracking/share/{token}      → PUBLIC — returns location for customer view
GET    /api/tracking/{id}               → detail
PATCH  /api/tracking/{id}/location      → update position + ETA
POST   /api/tracking/{id}/end           → end session
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.features.bookings.model_live_tracking import LiveTrackingSession
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/tracking", tags=["tracking"], dependencies=[Depends(require_module("pos"))])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _session_out(s: LiveTrackingSession) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "org_id": str(s.org_id),
        "appointment_id": str(s.appointment_id) if s.appointment_id else None,
        "staff_user_id": str(s.staff_user_id) if s.staff_user_id else None,
        "customer_id": str(s.customer_id) if s.customer_id else None,
        "share_token": s.share_token,
        "status": s.status,
        "current_lat": float(s.current_lat) if s.current_lat is not None else None,
        "current_lng": float(s.current_lng) if s.current_lng is not None else None,
        "eta_minutes": s.eta_minutes,
        "destination_lat": float(s.destination_lat) if s.destination_lat is not None else None,
        "destination_lng": float(s.destination_lng) if s.destination_lng is not None else None,
        "last_updated": s.last_updated.isoformat() if s.last_updated else None,
        "started_at": s.started_at.isoformat(),
        "ended_at": s.ended_at.isoformat() if s.ended_at else None,
        "created_at": s.created_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class SessionIn(BaseModel):
    appointment_id: Optional[uuid.UUID] = None
    staff_user_id: Optional[uuid.UUID] = None
    customer_id: Optional[uuid.UUID] = None
    destination_lat: Optional[Decimal] = None
    destination_lng: Optional[Decimal] = None


class LocationPatch(BaseModel):
    current_lat: Decimal
    current_lng: Decimal
    eta_minutes: Optional[int] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_sessions(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        rows = (
            await db.execute(
                select(LiveTrackingSession).where(
                    LiveTrackingSession.org_id == org_id,
                    LiveTrackingSession.status == "active",
                )
            )
        ).scalars().all()
        return [_session_out(s) for s in rows]
    except Exception as e:
        log.error("list_sessions failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def start_session(
    body: SessionIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        session = LiveTrackingSession(
            org_id=org_id,
            appointment_id=body.appointment_id,
            staff_user_id=body.staff_user_id,
            customer_id=body.customer_id,
            destination_lat=body.destination_lat,
            destination_lng=body.destination_lng,
            share_token=secrets.token_hex(32),
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return _session_out(session)
    except HTTPException:
        raise
    except Exception as e:
        log.error("start_session failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# Declare BEFORE /{session_id} to prevent path collision
@router.get("/share/{token}")
async def get_public_session(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Public endpoint — no auth required. Returns location data for customer view."""
    try:
        session = await db.scalar(
            select(LiveTrackingSession).where(
                LiveTrackingSession.share_token == token
            )
        )
        if not session:
            raise HTTPException(status_code=404, detail="Tracking session not found")
        return {
            "status": session.status,
            "current_lat": float(session.current_lat) if session.current_lat is not None else None,
            "current_lng": float(session.current_lng) if session.current_lng is not None else None,
            "eta_minutes": session.eta_minutes,
            "destination_lat": float(session.destination_lat) if session.destination_lat is not None else None,
            "destination_lng": float(session.destination_lng) if session.destination_lng is not None else None,
            "last_updated": session.last_updated.isoformat() if session.last_updated else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_public_session failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{session_id}")
async def get_session(
    session_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        session = await db.scalar(
            select(LiveTrackingSession).where(
                LiveTrackingSession.id == session_id,
                LiveTrackingSession.org_id == org_id,
            )
        )
        if not session:
            raise HTTPException(status_code=404, detail="Tracking session not found")
        return _session_out(session)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_session failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{session_id}/location")
async def update_location(
    session_id: uuid.UUID,
    body: LocationPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        session = await db.scalar(
            select(LiveTrackingSession).where(
                LiveTrackingSession.id == session_id,
                LiveTrackingSession.org_id == org_id,
            )
        )
        if not session:
            raise HTTPException(status_code=404, detail="Tracking session not found")
        if session.status == "ended":
            raise HTTPException(status_code=409, detail="Cannot update location on an ended session")

        session.current_lat = body.current_lat
        session.current_lng = body.current_lng
        if body.eta_minutes is not None:
            session.eta_minutes = body.eta_minutes
        session.last_updated = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(session)
        return _session_out(session)
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_location failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{session_id}/end")
async def end_session(
    session_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        session = await db.scalar(
            select(LiveTrackingSession).where(
                LiveTrackingSession.id == session_id,
                LiveTrackingSession.org_id == org_id,
            )
        )
        if not session:
            raise HTTPException(status_code=404, detail="Tracking session not found")

        session.status = "ended"
        session.ended_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(session)
        return _session_out(session)
    except HTTPException:
        raise
    except Exception as e:
        log.error("end_session failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
