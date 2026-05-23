"""Merchant Calendar Sync — Sprint 14

Endpoints:
  GET    /api/merchant-calendar-sync        list syncs for org
  POST   /api/merchant-calendar-sync        create/upsert sync
  GET    /api/merchant-calendar-sync/{id}   detail
  PATCH  /api/merchant-calendar-sync/{id}   update
  DELETE /api/merchant-calendar-sync/{id}   deactivate (is_active=False)
  POST   /api/merchant-calendar-sync/{id}/trigger-sync   manual sync trigger
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.merchant_calendar_sync import MerchantCalendarSync

router = APIRouter(prefix="/api/merchant-calendar-sync", tags=["integrations_calendar"])
log = logging.getLogger(__name__)

VALID_PROVIDERS = {"google", "outlook", "apple"}
VALID_DIRECTIONS = {"both", "push", "pull"}


def _org_user(ctx: tuple) -> tuple[uuid.UUID, uuid.UUID]:
    _, member = ctx
    return member.org_id, member.user_id


class CalendarSyncIn(BaseModel):
    provider: str
    calendar_id: Optional[str] = None
    sync_direction: str = "both"
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expiry: Optional[datetime] = None


class CalendarSyncPatch(BaseModel):
    calendar_id: Optional[str] = None
    sync_direction: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expiry: Optional[datetime] = None
    is_active: Optional[bool] = None


def _to_dict(obj: MerchantCalendarSync) -> dict:
    return {
        "id": str(obj.id),
        "org_id": str(obj.org_id),
        "user_id": str(obj.user_id),
        "provider": obj.provider,
        "calendar_id": obj.calendar_id,
        "sync_direction": obj.sync_direction,
        "last_synced_at": obj.last_synced_at.isoformat() if obj.last_synced_at else None,
        "is_active": obj.is_active,
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
        "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
    }


@router.get("")
async def list_syncs(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
):
    org_id, _ = _org_user(ctx)
    try:
        result = await db.execute(
            select(MerchantCalendarSync)
            .where(MerchantCalendarSync.org_id == org_id)
            .offset(skip)
            .limit(limit)
        )
        syncs = result.scalars().all()
        return {"items": [_to_dict(s) for s in syncs], "total": len(syncs)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_calendar_syncs failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_sync(
    body: CalendarSyncIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id, user_id = _org_user(ctx)
    try:
        if body.provider not in VALID_PROVIDERS:
            raise HTTPException(status_code=422, detail=f"provider must be one of {VALID_PROVIDERS}")
        if body.sync_direction not in VALID_DIRECTIONS:
            raise HTTPException(status_code=422, detail=f"sync_direction must be one of {VALID_DIRECTIONS}")

        sync = MerchantCalendarSync(
            org_id=org_id,
            user_id=user_id,
            provider=body.provider,
            calendar_id=body.calendar_id,
            sync_direction=body.sync_direction,
            access_token=body.access_token,
            refresh_token=body.refresh_token,
            token_expiry=body.token_expiry,
        )
        db.add(sync)
        await db.commit()
        await db.refresh(sync)
        return _to_dict(sync)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_calendar_sync failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{sync_id}")
async def get_sync(
    sync_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id, _ = _org_user(ctx)
    try:
        result = await db.execute(
            select(MerchantCalendarSync).where(
                MerchantCalendarSync.id == sync_id,
                MerchantCalendarSync.org_id == org_id,
            )
        )
        sync = result.scalar_one_or_none()
        if not sync:
            raise HTTPException(status_code=404, detail="Calendar sync not found")
        return _to_dict(sync)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_calendar_sync failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{sync_id}")
async def update_sync(
    sync_id: uuid.UUID,
    body: CalendarSyncPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id, _ = _org_user(ctx)
    try:
        result = await db.execute(
            select(MerchantCalendarSync).where(
                MerchantCalendarSync.id == sync_id,
                MerchantCalendarSync.org_id == org_id,
            )
        )
        sync = result.scalar_one_or_none()
        if not sync:
            raise HTTPException(status_code=404, detail="Calendar sync not found")

        if body.sync_direction is not None and body.sync_direction not in VALID_DIRECTIONS:
            raise HTTPException(status_code=422, detail=f"sync_direction must be one of {VALID_DIRECTIONS}")

        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(sync, field, value)

        await db.commit()
        await db.refresh(sync)
        return _to_dict(sync)
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_calendar_sync failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{sync_id}")
async def deactivate_sync(
    sync_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id, _ = _org_user(ctx)
    try:
        result = await db.execute(
            select(MerchantCalendarSync).where(
                MerchantCalendarSync.id == sync_id,
                MerchantCalendarSync.org_id == org_id,
            )
        )
        sync = result.scalar_one_or_none()
        if not sync:
            raise HTTPException(status_code=404, detail="Calendar sync not found")
        sync.is_active = False
        await db.commit()
        return {"deactivated": True, "id": str(sync_id)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("deactivate_calendar_sync failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{sync_id}/trigger-sync")
async def trigger_sync(
    sync_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id, _ = _org_user(ctx)
    try:
        result = await db.execute(
            select(MerchantCalendarSync).where(
                MerchantCalendarSync.id == sync_id,
                MerchantCalendarSync.org_id == org_id,
            )
        )
        sync = result.scalar_one_or_none()
        if not sync:
            raise HTTPException(status_code=404, detail="Calendar sync not found")
        if not sync.is_active:
            raise HTTPException(status_code=422, detail="Calendar sync is not active")

        sync.last_synced_at = datetime.now(timezone.utc)
        await db.commit()
        return {"triggered": True, "last_synced_at": sync.last_synced_at.isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        log.error("trigger_calendar_sync failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
