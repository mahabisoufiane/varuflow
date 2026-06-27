"""Home-screen widgets router — Sprint 15.  prefix /api/home-screen-widgets"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.features.mobile.home_screen_widget import HomeScreenWidget, WidgetDataSnapshot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/home-screen-widgets", tags=["home-screen-widgets"], dependencies=[Depends(require_module("dashboard"))])


def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.user_id


# ── Schemas ────────────────────────────────────────────────────────────────────

class WidgetOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    user_id: uuid.UUID
    widget_type: str
    platform: str
    widget_size: str
    config: Optional[Any]
    is_active: bool
    last_rendered_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WidgetIn(BaseModel):
    widget_type: str
    platform: str
    widget_size: str = "medium"
    config: Optional[Any] = None


class SnapshotOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    widget_type: str
    snapshot: Any
    generated_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[WidgetOut])
async def list_widgets(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        q = (
            select(HomeScreenWidget)
            .where(HomeScreenWidget.org_id == org_id, HomeScreenWidget.user_id == user_id)
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(q)
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_widgets failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/", response_model=WidgetOut, status_code=201)
async def upsert_widget(
    body: WidgetIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        stmt = (
            pg_insert(HomeScreenWidget)
            .values(
                org_id=org_id,
                user_id=user_id,
                widget_type=body.widget_type,
                platform=body.platform,
                widget_size=body.widget_size,
                config=body.config,
                is_active=True,
            )
            .on_conflict_do_update(
                constraint="uq_home_screen_widgets_org_user_type_platform",
                set_={
                    "widget_size": body.widget_size,
                    "config": body.config,
                    "is_active": True,
                    "updated_at": func.now(),
                },
            )
            .returning(HomeScreenWidget)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.scalar_one()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"upsert_widget failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{widget_id}", status_code=204)
async def delete_widget(
    widget_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        widget = await db.get(HomeScreenWidget, widget_id)
        if not widget or widget.org_id != org_id or widget.user_id != user_id:
            raise HTTPException(status_code=404, detail="Widget not found")
        await db.delete(widget)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_widget failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/snapshot/{widget_type}", response_model=SnapshotOut)
async def get_snapshot(
    widget_type: str,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        now = datetime.now(timezone.utc)
        q = select(WidgetDataSnapshot).where(
            WidgetDataSnapshot.org_id == org_id,
            WidgetDataSnapshot.widget_type == widget_type,
            WidgetDataSnapshot.expires_at > now,
        )
        result = await db.execute(q)
        snapshot = result.scalar_one_or_none()
        if not snapshot:
            raise HTTPException(status_code=404, detail="No valid snapshot found — call /refresh to generate one")
        return snapshot
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_snapshot failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/snapshot/{widget_type}/refresh", response_model=SnapshotOut)
async def refresh_snapshot(
    widget_type: str,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        expires_at = now + timedelta(minutes=15)

        if widget_type == "today_bookings":
            row = await db.execute(
                text(
                    "SELECT COUNT(*) FROM bookings "
                    "WHERE org_id = :org_id AND DATE(start_time AT TIME ZONE 'UTC') = DATE(:today)"
                    " AND deleted_at IS NULL"
                ),
                {"org_id": str(org_id), "today": today_start},
            )
            count = int(row.scalar() or 0)
            data: Any = {"count": count, "label": "Today's bookings"}

        elif widget_type == "today_revenue":
            row = await db.execute(
                text(
                    "SELECT COALESCE(SUM(total_amount), 0) FROM invoices "
                    "WHERE org_id = :org_id AND status = 'paid' "
                    "AND updated_at >= :start AND deleted_at IS NULL"
                ),
                {"org_id": str(org_id), "start": today_start},
            )
            total = float(row.scalar() or 0)
            data = {"amount": total, "currency": "SEK", "label": "Today's revenue"}

        elif widget_type == "low_stock":
            row = await db.execute(
                text(
                    "SELECT COUNT(*) FROM stock_levels "
                    "WHERE org_id = :org_id AND quantity <= reorder_point"
                ),
                {"org_id": str(org_id)},
            )
            count = int(row.scalar() or 0)
            data = {"count": count, "label": "Low stock items"}

        else:
            data = {"widget_type": widget_type, "message": "No data source configured"}

        stmt = (
            pg_insert(WidgetDataSnapshot)
            .values(
                org_id=org_id,
                widget_type=widget_type,
                snapshot=data,
                generated_at=now,
                expires_at=expires_at,
            )
            .on_conflict_do_update(
                constraint="uq_widget_data_snapshots_org_type",
                set_={
                    "snapshot": data,
                    "generated_at": now,
                    "expires_at": expires_at,
                },
            )
            .returning(WidgetDataSnapshot)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.scalar_one()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"refresh_snapshot failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
