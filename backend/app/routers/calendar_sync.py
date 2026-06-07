"""Calendar sync config endpoints — Sprint 10.

Endpoints under ``/api/calendar-sync``:

    GET    ""                                   get sync config for customer
    PUT    /{customer_id}/{provider}             upsert sync token/config
    DELETE /{customer_id}/{provider}             disable sync
    GET    /{customer_id}/ics                    generate iCal feed URL
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.calendar_sync import CalendarSyncToken
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/calendar-sync", tags=["calendar-sync"], dependencies=[Depends(require_module("hr"))])
logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────────────

class CalendarSyncUpsert(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    token_expiry: datetime | None = None
    calendar_id: str | None = None
    sync_enabled: bool = True


class CalendarSyncOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    provider: str
    calendar_id: str | None
    sync_enabled: bool
    token_expiry: datetime | None
    created_at: datetime
    updated_at: datetime


class IcsFeedOut(BaseModel):
    feed_url: str


def _to_out(row: CalendarSyncToken) -> CalendarSyncOut:
    return CalendarSyncOut(
        id=row.id,
        org_id=row.org_id,
        customer_id=row.customer_id,
        provider=row.provider,
        calendar_id=row.calendar_id,
        sync_enabled=row.sync_enabled,
        token_expiry=row.token_expiry,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[CalendarSyncOut])
async def list_sync_configs(
    customer_id: uuid.UUID = Query(...),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        stmt = select(CalendarSyncToken).where(
            CalendarSyncToken.org_id == member.org_id,
            CalendarSyncToken.customer_id == customer_id,
        )
        rows = (await db.scalars(stmt)).all()
        return [_to_out(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_sync_configs failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{customer_id}/{provider}", response_model=CalendarSyncOut)
async def upsert_sync_config(
    customer_id: uuid.UUID,
    provider: str,
    body: CalendarSyncUpsert,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        stmt = select(CalendarSyncToken).where(
            CalendarSyncToken.org_id == member.org_id,
            CalendarSyncToken.customer_id == customer_id,
            CalendarSyncToken.provider == provider,
        )
        row = (await db.scalars(stmt)).first()
        if row is None:
            row = CalendarSyncToken(
                org_id=member.org_id,
                customer_id=customer_id,
                provider=provider,
            )
            db.add(row)
        for field, val in body.model_dump(exclude_unset=True).items():
            setattr(row, field, val)
        await db.commit()
        await db.refresh(row)
        return _to_out(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"upsert_sync_config failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{customer_id}/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def disable_sync(
    customer_id: uuid.UUID,
    provider: str,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        stmt = select(CalendarSyncToken).where(
            CalendarSyncToken.org_id == member.org_id,
            CalendarSyncToken.customer_id == customer_id,
            CalendarSyncToken.provider == provider,
        )
        row = (await db.scalars(stmt)).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Sync config not found")
        row.sync_enabled = False
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"disable_sync failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{customer_id}/ics", response_model=IcsFeedOut)
async def get_ics_feed_url(
    customer_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        # ICS token is a deterministic combination of org_id + customer_id
        # Actual ICS generation happens at a separate public endpoint (future work)
        token = f"{member.org_id}-{customer_id}".replace("-", "")
        feed_url = f"/api/calendar-sync/feed/{token}.ics"
        return IcsFeedOut(feed_url=feed_url)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_ics_feed_url failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
