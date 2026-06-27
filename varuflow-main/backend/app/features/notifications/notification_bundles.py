"""Notification Bundle Configs — Sprint 14

Endpoints:
  GET    /api/notification-bundles        list bundles for user
  POST   /api/notification-bundles        create bundle
  GET    /api/notification-bundles/{id}   detail
  PATCH  /api/notification-bundles/{id}   update
  DELETE /api/notification-bundles/{id}   delete
"""
from __future__ import annotations

import logging
import uuid
from datetime import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from .notification_bundle import NotificationBundleConfig
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/notification-bundles", tags=["notifications"], dependencies=[Depends(require_module("settings"))])
log = logging.getLogger(__name__)

VALID_CHANNELS = {"push", "email", "sms", "in_app"}
VALID_SCHEDULES = {"immediate", "hourly", "daily", "weekly"}


def _org_user(ctx: tuple) -> tuple[uuid.UUID, uuid.UUID]:
    _, member = ctx
    return member.org_id, member.user_id


def _to_dict(b: NotificationBundleConfig) -> dict:
    return {
        "id": str(b.id),
        "org_id": str(b.org_id),
        "user_id": str(b.user_id),
        "bundle_name": b.bundle_name,
        "event_types": b.event_types,
        "delivery_channel": b.delivery_channel,
        "schedule": b.schedule,
        "digest_time": b.digest_time.isoformat() if b.digest_time else None,
        "is_active": b.is_active,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "updated_at": b.updated_at.isoformat() if b.updated_at else None,
    }


class BundleIn(BaseModel):
    bundle_name: str
    event_types: list[str] = []
    delivery_channel: str = "in_app"
    schedule: str = "immediate"
    digest_time: Optional[str] = None  # HH:MM format
    is_active: bool = True


class BundlePatch(BaseModel):
    bundle_name: Optional[str] = None
    event_types: Optional[list[str]] = None
    delivery_channel: Optional[str] = None
    schedule: Optional[str] = None
    digest_time: Optional[str] = None
    is_active: Optional[bool] = None


def _parse_time(t: Optional[str]) -> Optional[time]:
    if not t:
        return None
    try:
        parts = t.split(":")
        return time(int(parts[0]), int(parts[1]))
    except Exception:
        raise HTTPException(status_code=422, detail="digest_time must be HH:MM format")


@router.get("")
async def list_bundles(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
):
    org_id, user_id = _org_user(ctx)
    try:
        result = await db.execute(
            select(NotificationBundleConfig)
            .where(
                NotificationBundleConfig.org_id == org_id,
                NotificationBundleConfig.user_id == user_id,
            )
            .offset(skip)
            .limit(limit)
        )
        bundles = result.scalars().all()
        return {"items": [_to_dict(b) for b in bundles], "total": len(bundles)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_notification_bundles failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_bundle(
    body: BundleIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id, user_id = _org_user(ctx)
    try:
        if body.delivery_channel not in VALID_CHANNELS:
            raise HTTPException(status_code=422, detail=f"delivery_channel must be one of {VALID_CHANNELS}")
        if body.schedule not in VALID_SCHEDULES:
            raise HTTPException(status_code=422, detail=f"schedule must be one of {VALID_SCHEDULES}")

        bundle = NotificationBundleConfig(
            org_id=org_id,
            user_id=user_id,
            bundle_name=body.bundle_name,
            event_types=body.event_types,
            delivery_channel=body.delivery_channel,
            schedule=body.schedule,
            digest_time=_parse_time(body.digest_time),
            is_active=body.is_active,
        )
        db.add(bundle)
        await db.commit()
        await db.refresh(bundle)
        return _to_dict(bundle)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_notification_bundle failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{bundle_id}")
async def get_bundle(
    bundle_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id, user_id = _org_user(ctx)
    try:
        result = await db.execute(
            select(NotificationBundleConfig).where(
                NotificationBundleConfig.id == bundle_id,
                NotificationBundleConfig.org_id == org_id,
                NotificationBundleConfig.user_id == user_id,
            )
        )
        bundle = result.scalar_one_or_none()
        if not bundle:
            raise HTTPException(status_code=404, detail="Notification bundle not found")
        return _to_dict(bundle)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_notification_bundle failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{bundle_id}")
async def update_bundle(
    bundle_id: uuid.UUID,
    body: BundlePatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id, user_id = _org_user(ctx)
    try:
        result = await db.execute(
            select(NotificationBundleConfig).where(
                NotificationBundleConfig.id == bundle_id,
                NotificationBundleConfig.org_id == org_id,
                NotificationBundleConfig.user_id == user_id,
            )
        )
        bundle = result.scalar_one_or_none()
        if not bundle:
            raise HTTPException(status_code=404, detail="Notification bundle not found")

        data = body.model_dump(exclude_unset=True)
        if "delivery_channel" in data and data["delivery_channel"] not in VALID_CHANNELS:
            raise HTTPException(status_code=422, detail=f"delivery_channel must be one of {VALID_CHANNELS}")
        if "schedule" in data and data["schedule"] not in VALID_SCHEDULES:
            raise HTTPException(status_code=422, detail=f"schedule must be one of {VALID_SCHEDULES}")

        if "digest_time" in data:
            bundle.digest_time = _parse_time(data.pop("digest_time"))

        for field, value in data.items():
            setattr(bundle, field, value)

        await db.commit()
        await db.refresh(bundle)
        return _to_dict(bundle)
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_notification_bundle failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{bundle_id}")
async def delete_bundle(
    bundle_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id, user_id = _org_user(ctx)
    try:
        result = await db.execute(
            select(NotificationBundleConfig).where(
                NotificationBundleConfig.id == bundle_id,
                NotificationBundleConfig.org_id == org_id,
                NotificationBundleConfig.user_id == user_id,
            )
        )
        bundle = result.scalar_one_or_none()
        if not bundle:
            raise HTTPException(status_code=404, detail="Notification bundle not found")
        await db.delete(bundle)
        await db.commit()
        return {"deleted": True, "id": str(bundle_id)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_notification_bundle failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
