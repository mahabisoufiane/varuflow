"""Customer app configuration router — app branding, push tokens, and stats.

Endpoints
─────────
GET    /api/customer-app/config             → get (or create default) app config for org
PATCH  /api/customer-app/config             → update app config
POST   /api/customer-app/push-tokens        → register / upsert push token
DELETE /api/customer-app/push-tokens/{id}   → remove push token
GET    /api/customer-app/push-tokens        → list tokens for org (admin view)
GET    /api/customer-app/stats              → device stats for org
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.customer_app import CustomerAppConfig, CustomerAppPushToken
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/customer-app", tags=["customer-app"], dependencies=[Depends(require_module("settings"))])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _config_out(c: CustomerAppConfig) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "org_id": str(c.org_id),
        "app_name": c.app_name,
        "primary_color": c.primary_color,
        "secondary_color": c.secondary_color,
        "logo_url": c.logo_url,
        "welcome_message": c.welcome_message,
        "features_enabled": c.features_enabled,
        "booking_enabled": c.booking_enabled,
        "loyalty_enabled": c.loyalty_enabled,
        "notifications_enabled": c.notifications_enabled,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
    }


def _token_out(t: CustomerAppPushToken) -> dict[str, Any]:
    return {
        "id": str(t.id),
        "org_id": str(t.org_id),
        "customer_id": str(t.customer_id),
        "token": t.token,
        "platform": t.platform,
        "app_version": t.app_version,
        "created_at": t.created_at.isoformat(),
        "last_seen_at": t.last_seen_at.isoformat() if t.last_seen_at else None,
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class AppConfigPatch(BaseModel):
    app_name: Optional[str] = Field(default=None, max_length=100)
    primary_color: Optional[str] = Field(default=None, max_length=7)
    secondary_color: Optional[str] = Field(default=None, max_length=7)
    logo_url: Optional[str] = None
    welcome_message: Optional[str] = None
    booking_enabled: Optional[bool] = None
    loyalty_enabled: Optional[bool] = None
    notifications_enabled: Optional[bool] = None
    features_enabled: Optional[dict] = None


class PushTokenIn(BaseModel):
    customer_id: uuid.UUID
    token: str = Field(min_length=1, max_length=500)
    platform: str = Field(min_length=1, max_length=20)
    app_version: Optional[str] = Field(default=None, max_length=20)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/config")
async def get_app_config(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        config = await db.scalar(
            select(CustomerAppConfig).where(CustomerAppConfig.org_id == org_id)
        )
        if not config:
            # Create default config
            config = CustomerAppConfig(
                org_id=org_id,
                app_name="My App",
            )
            db.add(config)
            await db.commit()
            await db.refresh(config)
        return _config_out(config)
    except Exception as e:
        log.error("get_app_config failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/config")
async def update_app_config(
    body: AppConfigPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        config = await db.scalar(
            select(CustomerAppConfig).where(CustomerAppConfig.org_id == org_id)
        )
        if not config:
            config = CustomerAppConfig(
                org_id=org_id,
                app_name=body.app_name or "My App",
            )
            db.add(config)
            await db.flush()

        if body.app_name is not None:
            config.app_name = body.app_name
        if body.primary_color is not None:
            config.primary_color = body.primary_color
        if body.secondary_color is not None:
            config.secondary_color = body.secondary_color
        if body.logo_url is not None:
            config.logo_url = body.logo_url
        if body.welcome_message is not None:
            config.welcome_message = body.welcome_message
        if body.booking_enabled is not None:
            config.booking_enabled = body.booking_enabled
        if body.loyalty_enabled is not None:
            config.loyalty_enabled = body.loyalty_enabled
        if body.notifications_enabled is not None:
            config.notifications_enabled = body.notifications_enabled
        if body.features_enabled is not None:
            config.features_enabled = body.features_enabled

        await db.commit()
        await db.refresh(config)
        return _config_out(config)
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_app_config failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/push-tokens", status_code=201)
async def register_push_token(
    body: PushTokenIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        now = datetime.now(timezone.utc)

        # Upsert on (customer_id, token) unique constraint
        stmt = (
            pg_insert(CustomerAppPushToken)
            .values(
                id=uuid.uuid4(),
                org_id=org_id,
                customer_id=body.customer_id,
                token=body.token,
                platform=body.platform,
                app_version=body.app_version,
                created_at=now,
                last_seen_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_customer_app_push_token",
                set_={"last_seen_at": now, "app_version": body.app_version},
            )
            .returning(CustomerAppPushToken)
        )
        result = await db.execute(stmt)
        token_row = result.scalars().first()
        await db.commit()

        if token_row is None:
            # Fallback: fetch the row after upsert
            token_row = await db.scalar(
                select(CustomerAppPushToken).where(
                    CustomerAppPushToken.customer_id == body.customer_id,
                    CustomerAppPushToken.token == body.token,
                )
            )

        return _token_out(token_row)
    except HTTPException:
        raise
    except Exception as e:
        log.error("register_push_token failed: %s", e, extra={"org_id": str(org_id)})  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/push-tokens/{token_id}", status_code=204)
async def delete_push_token(
    token_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        token = await db.scalar(
            select(CustomerAppPushToken).where(
                CustomerAppPushToken.id == token_id,
                CustomerAppPushToken.org_id == org_id,
            )
        )
        if not token:
            raise HTTPException(status_code=404, detail="Push token not found")
        await db.delete(token)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_push_token failed: %s", e, extra={"org_id": str(org_id)})  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/push-tokens")
async def list_push_tokens(
    customer_id: Optional[uuid.UUID] = Query(default=None),
    platform: Optional[str] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = select(CustomerAppPushToken).where(CustomerAppPushToken.org_id == org_id)
        if customer_id:
            q = q.where(CustomerAppPushToken.customer_id == customer_id)
        if platform:
            q = q.where(CustomerAppPushToken.platform == platform)
        q = q.order_by(CustomerAppPushToken.created_at)
        tokens = (await db.execute(q)).scalars().all()
        return [_token_out(t) for t in tokens]
    except Exception as e:
        log.error("list_push_tokens failed: %s", e, extra={"org_id": str(org_id)})  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats")
async def get_app_stats(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        total = (await db.scalar(
            select(func.count(CustomerAppPushToken.id))
            .where(CustomerAppPushToken.org_id == org_id)
        )) or 0

        # By-platform breakdown
        platform_rows = (await db.execute(
            select(CustomerAppPushToken.platform, func.count(CustomerAppPushToken.id))
            .where(CustomerAppPushToken.org_id == org_id)
            .group_by(CustomerAppPushToken.platform)
        )).all()
        by_platform = {row[0]: row[1] for row in platform_rows}

        # Active = last_seen_at within 30 days
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        active = (await db.scalar(
            select(func.count(CustomerAppPushToken.id))
            .where(
                CustomerAppPushToken.org_id == org_id,
                CustomerAppPushToken.last_seen_at >= cutoff,
            )
        )) or 0

        return {
            "total_registered_devices": total,
            "by_platform": by_platform,
            "active_tokens_last_30_days": active,
        }
    except Exception as e:
        log.error("get_app_stats failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
