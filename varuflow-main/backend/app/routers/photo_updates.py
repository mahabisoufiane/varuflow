"""Photo Updates — progress photos sent to customers during service.

Endpoints
─────────
GET    /api/photos                              → list photo updates for org
POST   /api/photos                              → send photo update
GET    /api/photos/appointment/{appointment_id} → list for appointment
GET    /api/photos/{id}                         → detail
PATCH  /api/photos/{id}/view                    → mark viewed
DELETE /api/photos/{id}                         → delete
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
from app.models.service_photo_update import ServicePhotoUpdate

router = APIRouter(prefix="/api/photos", tags=["photos"])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    user, _ = ctx
    return uuid.UUID(str(user["user_id"]))


def _photo_out(p: ServicePhotoUpdate) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "org_id": str(p.org_id),
        "appointment_id": str(p.appointment_id) if p.appointment_id else None,
        "customer_id": str(p.customer_id) if p.customer_id else None,
        "sent_by": str(p.sent_by) if p.sent_by else None,
        "photo_url": p.photo_url,
        "caption": p.caption,
        "is_viewed": p.is_viewed,
        "viewed_at": p.viewed_at.isoformat() if p.viewed_at else None,
        "created_at": p.created_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class PhotoIn(BaseModel):
    appointment_id: Optional[uuid.UUID] = None
    customer_id: Optional[uuid.UUID] = None
    photo_url: str = Field(min_length=1)
    caption: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_photos(
    appointment_id: Optional[uuid.UUID] = Query(default=None),
    customer_id: Optional[uuid.UUID] = Query(default=None),
    is_viewed: Optional[bool] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = select(ServicePhotoUpdate).where(ServicePhotoUpdate.org_id == org_id)
        if appointment_id:
            q = q.where(ServicePhotoUpdate.appointment_id == appointment_id)
        if customer_id:
            q = q.where(ServicePhotoUpdate.customer_id == customer_id)
        if is_viewed is not None:
            q = q.where(ServicePhotoUpdate.is_viewed == is_viewed)
        q = q.order_by(ServicePhotoUpdate.created_at.desc())
        photos = (await db.execute(q)).scalars().all()
        return [_photo_out(p) for p in photos]
    except Exception as e:
        log.error("list_photos failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def send_photo(
    body: PhotoIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    try:
        photo = ServicePhotoUpdate(
            org_id=org_id,
            appointment_id=body.appointment_id,
            customer_id=body.customer_id,
            sent_by=user_id,
            photo_url=body.photo_url,
            caption=body.caption,
        )
        db.add(photo)
        await db.commit()
        await db.refresh(photo)
        return _photo_out(photo)
    except HTTPException:
        raise
    except Exception as e:
        log.error("send_photo failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# Declare BEFORE /{photo_id} to prevent path collision
@router.get("/appointment/{appointment_id}")
async def list_photos_for_appointment(
    appointment_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = (
            select(ServicePhotoUpdate)
            .where(
                ServicePhotoUpdate.org_id == org_id,
                ServicePhotoUpdate.appointment_id == appointment_id,
            )
            .order_by(ServicePhotoUpdate.created_at.desc())
        )
        photos = (await db.execute(q)).scalars().all()
        return [_photo_out(p) for p in photos]
    except Exception as e:
        log.error(
            "list_photos_for_appointment failed: %s", e,
            extra={"org_id": str(org_id)},
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{photo_id}")
async def get_photo(
    photo_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        photo = await db.scalar(
            select(ServicePhotoUpdate).where(
                ServicePhotoUpdate.id == photo_id,
                ServicePhotoUpdate.org_id == org_id,
            )
        )
        if not photo:
            raise HTTPException(status_code=404, detail="Photo update not found")
        return _photo_out(photo)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_photo failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{photo_id}/view")
async def mark_viewed(
    photo_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        photo = await db.scalar(
            select(ServicePhotoUpdate).where(
                ServicePhotoUpdate.id == photo_id,
                ServicePhotoUpdate.org_id == org_id,
            )
        )
        if not photo:
            raise HTTPException(status_code=404, detail="Photo update not found")

        photo.is_viewed = True
        photo.viewed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(photo)
        return _photo_out(photo)
    except HTTPException:
        raise
    except Exception as e:
        log.error("mark_viewed failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{photo_id}", status_code=204)
async def delete_photo(
    photo_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        photo = await db.scalar(
            select(ServicePhotoUpdate).where(
                ServicePhotoUpdate.id == photo_id,
                ServicePhotoUpdate.org_id == org_id,
            )
        )
        if not photo:
            raise HTTPException(status_code=404, detail="Photo update not found")
        await db.delete(photo)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_photo failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
