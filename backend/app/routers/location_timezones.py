"""Org Location Timezones — Sprint 14

Endpoints:
  GET    /api/location-timezones          list for org
  POST   /api/location-timezones          create (location_name, timezone, is_default)
  PATCH  /api/location-timezones/{id}     update
  DELETE /api/location-timezones/{id}     delete
  POST   /api/location-timezones/{id}/set-default   mark as default (unsets others)
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.location_timezone import OrgLocationTimezone

router = APIRouter(prefix="/api/location-timezones", tags=["settings"])
log = logging.getLogger(__name__)


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _to_dict(t: OrgLocationTimezone) -> dict:
    return {
        "id": str(t.id),
        "org_id": str(t.org_id),
        "location_name": t.location_name,
        "timezone": t.timezone,
        "is_default": t.is_default,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


class TimezoneIn(BaseModel):
    location_name: str
    timezone: str
    is_default: bool = False


class TimezonePatch(BaseModel):
    location_name: Optional[str] = None
    timezone: Optional[str] = None
    is_default: Optional[bool] = None


@router.get("")
async def list_timezones(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
):
    org_id = _org(ctx)
    try:
        result = await db.execute(
            select(OrgLocationTimezone)
            .where(OrgLocationTimezone.org_id == org_id)
            .offset(skip)
            .limit(limit)
        )
        timezones = result.scalars().all()
        return {"items": [_to_dict(t) for t in timezones], "total": len(timezones)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_location_timezones failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_timezone(
    body: TimezoneIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        if body.is_default:
            await db.execute(
                update(OrgLocationTimezone)
                .where(OrgLocationTimezone.org_id == org_id)
                .values(is_default=False)
            )

        tz = OrgLocationTimezone(
            org_id=org_id,
            location_name=body.location_name,
            timezone=body.timezone,
            is_default=body.is_default,
        )
        db.add(tz)
        await db.commit()
        await db.refresh(tz)
        return _to_dict(tz)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_location_timezone failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{tz_id}")
async def update_timezone(
    tz_id: uuid.UUID,
    body: TimezonePatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        result = await db.execute(
            select(OrgLocationTimezone).where(
                OrgLocationTimezone.id == tz_id,
                OrgLocationTimezone.org_id == org_id,
            )
        )
        tz = result.scalar_one_or_none()
        if not tz:
            raise HTTPException(status_code=404, detail="Location timezone not found")

        data = body.model_dump(exclude_unset=True)
        if data.get("is_default"):
            await db.execute(
                update(OrgLocationTimezone)
                .where(OrgLocationTimezone.org_id == org_id, OrgLocationTimezone.id != tz_id)
                .values(is_default=False)
            )

        for field, value in data.items():
            setattr(tz, field, value)

        await db.commit()
        await db.refresh(tz)
        return _to_dict(tz)
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_location_timezone failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{tz_id}")
async def delete_timezone(
    tz_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        result = await db.execute(
            select(OrgLocationTimezone).where(
                OrgLocationTimezone.id == tz_id,
                OrgLocationTimezone.org_id == org_id,
            )
        )
        tz = result.scalar_one_or_none()
        if not tz:
            raise HTTPException(status_code=404, detail="Location timezone not found")
        await db.delete(tz)
        await db.commit()
        return {"deleted": True, "id": str(tz_id)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_location_timezone failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{tz_id}/set-default")
async def set_default_timezone(
    tz_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        result = await db.execute(
            select(OrgLocationTimezone).where(
                OrgLocationTimezone.id == tz_id,
                OrgLocationTimezone.org_id == org_id,
            )
        )
        tz = result.scalar_one_or_none()
        if not tz:
            raise HTTPException(status_code=404, detail="Location timezone not found")

        # Unset all others
        await db.execute(
            update(OrgLocationTimezone)
            .where(OrgLocationTimezone.org_id == org_id)
            .values(is_default=False)
        )
        tz.is_default = True
        await db.commit()
        await db.refresh(tz)
        return _to_dict(tz)
    except HTTPException:
        raise
    except Exception as e:
        log.error("set_default_location_timezone failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
