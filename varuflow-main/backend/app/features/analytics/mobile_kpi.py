"""Mobile KPI router — Sprint 13.  prefix /api/mobile"""
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
from app.features.mobile.mobile_kpi_config import MobileKpiConfig
from app.features.notifications.push_notification_token import PushNotificationToken
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mobile", tags=["mobile-kpi"], dependencies=[Depends(require_module("analytics"))])


def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.user_id


# ── Schemas ────────────────────────────────────────────────────────────────────

class KpiConfigOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    user_id: uuid.UUID
    kpi_ids: list
    notification_deep_links_enabled: bool
    refresh_interval_minutes: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KpiConfigIn(BaseModel):
    kpi_ids: list[str] = []
    notification_deep_links_enabled: bool = True
    refresh_interval_minutes: int = 15


class KpiValueOut(BaseModel):
    key: str
    label: str
    value: Any
    unit: str
    change_pct: Optional[float]


class PushTokenIn(BaseModel):
    token: str
    platform: str = "web"
    device_label: Optional[str] = None


class PushTokenOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    user_id: uuid.UUID
    token: str
    platform: str
    device_label: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/kpi-config", response_model=KpiConfigOut)
async def get_kpi_config(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        q = select(MobileKpiConfig).where(
            MobileKpiConfig.org_id == org_id,
            MobileKpiConfig.user_id == user_id,
        )
        result = await db.execute(q)
        cfg = result.scalar_one_or_none()
        if not cfg:
            cfg = MobileKpiConfig(org_id=org_id, user_id=user_id)
            db.add(cfg)
            await db.commit()
            await db.refresh(cfg)
        return cfg
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_kpi_config failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/kpi-config", response_model=KpiConfigOut)
async def upsert_kpi_config(
    body: KpiConfigIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        stmt = (
            pg_insert(MobileKpiConfig)
            .values(
                org_id=org_id,
                user_id=user_id,
                kpi_ids=body.kpi_ids,
                notification_deep_links_enabled=body.notification_deep_links_enabled,
                refresh_interval_minutes=body.refresh_interval_minutes,
            )
            .on_conflict_do_update(
                constraint="uq_mobile_kpi_configs_org_user",
                set_={
                    "kpi_ids": body.kpi_ids,
                    "notification_deep_links_enabled": body.notification_deep_links_enabled,
                    "refresh_interval_minutes": body.refresh_interval_minutes,
                    "updated_at": func.now(),
                },
            )
            .returning(MobileKpiConfig)
        )
        result = await db.execute(stmt)
        await db.commit()
        cfg = result.scalar_one()
        return cfg
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"upsert_kpi_config failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/kpis", response_model=list[KpiValueOut])
async def get_live_kpis(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = today_start.replace(day=1)
        last_month_start = (month_start - timedelta(days=1)).replace(day=1)
        thirty_days_ago = today_start - timedelta(days=30)

        # Today's revenue (sum of paid invoice amounts)
        rev_today = await db.execute(
            text(
                "SELECT COALESCE(SUM(total_amount), 0) FROM invoices "
                "WHERE org_id = :org_id AND status = 'paid' "
                "AND updated_at >= :start AND deleted_at IS NULL"
            ),
            {"org_id": str(org_id), "start": today_start},
        )
        revenue_today = float(rev_today.scalar() or 0)

        # Last month's revenue for comparison
        rev_last_month = await db.execute(
            text(
                "SELECT COALESCE(SUM(total_amount), 0) FROM invoices "
                "WHERE org_id = :org_id AND status = 'paid' "
                "AND updated_at >= :start AND updated_at < :end AND deleted_at IS NULL"
            ),
            {"org_id": str(org_id), "start": last_month_start, "end": month_start},
        )
        revenue_lm = float(rev_last_month.scalar() or 0)

        # Invoice count today
        inv_count = await db.execute(
            text(
                "SELECT COUNT(*) FROM invoices "
                "WHERE org_id = :org_id AND created_at >= :start AND deleted_at IS NULL"
            ),
            {"org_id": str(org_id), "start": today_start},
        )
        invoice_count = int(inv_count.scalar() or 0)

        # Outstanding balance
        outstanding = await db.execute(
            text(
                "SELECT COALESCE(SUM(total_amount), 0) FROM invoices "
                "WHERE org_id = :org_id AND status IN ('sent', 'overdue') AND deleted_at IS NULL"
            ),
            {"org_id": str(org_id)},
        )
        outstanding_balance = float(outstanding.scalar() or 0)

        # New customers last 30 days
        new_customers = await db.execute(
            text(
                "SELECT COUNT(*) FROM customers "
                "WHERE org_id = :org_id AND created_at >= :start AND deleted_at IS NULL"
            ),
            {"org_id": str(org_id), "start": thirty_days_ago},
        )
        new_cust_count = int(new_customers.scalar() or 0)

        change_rev = None
        if revenue_lm > 0:
            change_rev = round((revenue_today - revenue_lm) / revenue_lm * 100, 1)

        return [
            KpiValueOut(key="revenue_today", label="Today's Revenue", value=revenue_today, unit="SEK", change_pct=change_rev),
            KpiValueOut(key="invoice_count_today", label="Invoices Today", value=invoice_count, unit="pcs", change_pct=None),
            KpiValueOut(key="outstanding_balance", label="Outstanding Balance", value=outstanding_balance, unit="SEK", change_pct=None),
            KpiValueOut(key="new_customers_30d", label="New Customers (30d)", value=new_cust_count, unit="customers", change_pct=None),
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_live_kpis failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/push-tokens", response_model=list[PushTokenOut])
async def list_push_tokens(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        q = select(PushNotificationToken).where(
            PushNotificationToken.org_id == org_id,
            PushNotificationToken.user_id == user_id,
            PushNotificationToken.is_active.is_(True),
        )
        result = await db.execute(q)
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_push_tokens failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/push-tokens", response_model=PushTokenOut, status_code=201)
async def register_push_token(
    body: PushTokenIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        stmt = (
            pg_insert(PushNotificationToken)
            .values(
                org_id=org_id,
                user_id=user_id,
                token=body.token,
                platform=body.platform,
                device_label=body.device_label,
                is_active=True,
            )
            .on_conflict_do_update(
                constraint="uq_push_notification_tokens_org_user_token",
                set_={
                    "platform": body.platform,
                    "device_label": body.device_label,
                    "is_active": True,
                    "updated_at": func.now(),
                },
            )
            .returning(PushNotificationToken)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.scalar_one()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"register_push_token failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/push-tokens/{token_id}", status_code=204)
async def deactivate_push_token(
    token_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        tok = await db.get(PushNotificationToken, token_id)
        if not tok or tok.org_id != org_id or tok.user_id != user_id:
            raise HTTPException(status_code=404, detail="Push token not found")
        tok.is_active = False
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"deactivate_push_token failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
