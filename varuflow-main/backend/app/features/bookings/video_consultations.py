"""Video consultation rooms.

Endpoints
─────────
GET  /api/video                  → list consultations for org
POST /api/video                  → create consultation
GET  /api/video/{id}             → detail
PATCH /api/video/{id}            → update notes / staff / scheduled_for
POST /api/video/{id}/start       → set active + started_at
POST /api/video/{id}/end         → set ended + duration
POST /api/video/{id}/cancel      → set cancelled
DELETE /api/video/{id}           → delete if scheduled/cancelled
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.features.bookings.video_consultation import VideoConsultation
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/video", tags=["video-consultations"], dependencies=[Depends(require_module("crm"))])
log = logging.getLogger(__name__)

_DELETABLE_STATUSES = {"scheduled", "cancelled"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    user, _ = ctx
    return uuid.UUID(str(user["user_id"]))


def _vc_out(vc: VideoConsultation) -> dict[str, Any]:
    return {
        "id": str(vc.id),
        "org_id": str(vc.org_id),
        "customer_id": str(vc.customer_id) if vc.customer_id else None,
        "appointment_id": str(vc.appointment_id) if vc.appointment_id else None,
        "staff_user_id": str(vc.staff_user_id) if vc.staff_user_id else None,
        "provider": vc.provider,
        "room_name": vc.room_name,
        "room_url": vc.room_url,
        "staff_join_token": vc.staff_join_token,
        "customer_join_token": vc.customer_join_token,
        "status": vc.status,
        "scheduled_for": vc.scheduled_for.isoformat(),
        "started_at": vc.started_at.isoformat() if vc.started_at else None,
        "ended_at": vc.ended_at.isoformat() if vc.ended_at else None,
        "duration_seconds": vc.duration_seconds,
        "recording_url": vc.recording_url,
        "notes": vc.notes,
        "created_at": vc.created_at.isoformat(),
        "updated_at": vc.updated_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class VideoConsultationIn(BaseModel):
    customer_id: Optional[uuid.UUID] = None
    appointment_id: Optional[uuid.UUID] = None
    staff_user_id: Optional[uuid.UUID] = None
    provider: str = Field(default="daily", max_length=20)
    scheduled_for: datetime
    notes: Optional[str] = None


class VideoConsultationPatch(BaseModel):
    notes: Optional[str] = None
    staff_user_id: Optional[uuid.UUID] = None
    scheduled_for: Optional[datetime] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_consultations(
    status: Optional[str] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = select(VideoConsultation).where(VideoConsultation.org_id == org_id)
        if status:
            q = q.where(VideoConsultation.status == status)
        q = q.order_by(VideoConsultation.scheduled_for.desc())
        vcs = (await db.execute(q)).scalars().all()
        return [_vc_out(v) for v in vcs]
    except Exception as e:
        log.error("list_consultations failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_consultation(
    body: VideoConsultationIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        org_hex = org_id.hex[:8]
        room_name = f"varuflow-{org_hex}-{secrets.token_hex(6)}"
        staff_join_token = secrets.token_urlsafe(32)
        customer_join_token = secrets.token_urlsafe(32)
        room_url = (
            f"https://varuflow.daily.co/{room_name}"
            if body.provider == "daily"
            else None
        )

        vc = VideoConsultation(
            org_id=org_id,
            customer_id=body.customer_id,
            appointment_id=body.appointment_id,
            staff_user_id=body.staff_user_id,
            provider=body.provider,
            room_name=room_name,
            room_url=room_url,
            staff_join_token=staff_join_token,
            customer_join_token=customer_join_token,
            scheduled_for=body.scheduled_for,
            notes=body.notes,
        )
        db.add(vc)
        await db.commit()
        await db.refresh(vc)
        return _vc_out(vc)
    except Exception as e:
        log.error("create_consultation failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{vc_id}")
async def get_consultation(
    vc_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        vc = await db.scalar(
            select(VideoConsultation).where(
                VideoConsultation.id == vc_id,
                VideoConsultation.org_id == org_id,
            )
        )
        if not vc:
            raise HTTPException(status_code=404, detail="Consultation not found")
        return _vc_out(vc)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_consultation failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{vc_id}")
async def patch_consultation(
    vc_id: uuid.UUID,
    body: VideoConsultationPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        vc = await db.scalar(
            select(VideoConsultation).where(
                VideoConsultation.id == vc_id,
                VideoConsultation.org_id == org_id,
            )
        )
        if not vc:
            raise HTTPException(status_code=404, detail="Consultation not found")

        if body.notes is not None:
            vc.notes = body.notes
        if body.staff_user_id is not None:
            vc.staff_user_id = body.staff_user_id
        if body.scheduled_for is not None:
            vc.scheduled_for = body.scheduled_for

        vc.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(vc)
        return _vc_out(vc)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_consultation failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{vc_id}/start")
async def start_consultation(
    vc_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        vc = await db.scalar(
            select(VideoConsultation).where(
                VideoConsultation.id == vc_id,
                VideoConsultation.org_id == org_id,
            )
        )
        if not vc:
            raise HTTPException(status_code=404, detail="Consultation not found")

        now = datetime.now(timezone.utc)
        vc.status = "active"
        vc.started_at = now
        vc.updated_at = now
        await db.commit()
        await db.refresh(vc)
        return _vc_out(vc)
    except HTTPException:
        raise
    except Exception as e:
        log.error("start_consultation failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{vc_id}/end")
async def end_consultation(
    vc_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        vc = await db.scalar(
            select(VideoConsultation).where(
                VideoConsultation.id == vc_id,
                VideoConsultation.org_id == org_id,
            )
        )
        if not vc:
            raise HTTPException(status_code=404, detail="Consultation not found")

        now = datetime.now(timezone.utc)
        vc.status = "ended"
        vc.ended_at = now
        vc.updated_at = now
        if vc.started_at:
            delta = now - vc.started_at
            vc.duration_seconds = int(delta.total_seconds())
        await db.commit()
        await db.refresh(vc)
        return _vc_out(vc)
    except HTTPException:
        raise
    except Exception as e:
        log.error("end_consultation failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{vc_id}/cancel")
async def cancel_consultation(
    vc_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        vc = await db.scalar(
            select(VideoConsultation).where(
                VideoConsultation.id == vc_id,
                VideoConsultation.org_id == org_id,
            )
        )
        if not vc:
            raise HTTPException(status_code=404, detail="Consultation not found")

        vc.status = "cancelled"
        vc.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(vc)
        return _vc_out(vc)
    except HTTPException:
        raise
    except Exception as e:
        log.error("cancel_consultation failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{vc_id}", status_code=204)
async def delete_consultation(
    vc_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Only consultations in scheduled or cancelled state may be deleted."""
    org_id = _org_id(ctx)
    try:
        vc = await db.scalar(
            select(VideoConsultation).where(
                VideoConsultation.id == vc_id,
                VideoConsultation.org_id == org_id,
            )
        )
        if not vc:
            raise HTTPException(status_code=404, detail="Consultation not found")
        if vc.status not in _DELETABLE_STATUSES:
            raise HTTPException(
                status_code=422,
                detail="Only scheduled or cancelled consultations can be deleted",
            )
        await db.delete(vc)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_consultation failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
