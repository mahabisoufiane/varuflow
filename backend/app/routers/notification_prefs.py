"""Customer notification preferences.

Endpoints
─────────
GET /api/notification-prefs/{customer_id}  → get prefs (returns defaults if not set)
PUT /api/notification-prefs/{customer_id}  → upsert prefs
GET /api/notification-prefs               → list all customer prefs for the org
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.customer_notification_pref import CustomerNotificationPref

router = APIRouter(prefix="/api/notification-prefs", tags=["notification-prefs"])
log = logging.getLogger(__name__)

_DEFAULTS = {
    "remind_1_day": True,
    "remind_1_hour": True,
    "channel_push": True,
    "channel_email": True,
    "channel_sms": False,
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _pref_out(pref: CustomerNotificationPref) -> dict[str, Any]:
    return {
        "id": str(pref.id),
        "org_id": str(pref.org_id),
        "customer_id": str(pref.customer_id),
        "remind_1_day": pref.remind_1_day,
        "remind_1_hour": pref.remind_1_hour,
        "channel_push": pref.channel_push,
        "channel_email": pref.channel_email,
        "channel_sms": pref.channel_sms,
        "created_at": pref.created_at.isoformat(),
        "updated_at": pref.updated_at.isoformat(),
    }


def _default_pref(org_id: uuid.UUID, customer_id: uuid.UUID) -> dict[str, Any]:
    """Return a virtual default preferences object without touching the DB."""
    return {
        "id": None,
        "org_id": str(org_id),
        "customer_id": str(customer_id),
        **_DEFAULTS,
        "created_at": None,
        "updated_at": None,
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class NotificationPrefIn(BaseModel):
    remind_1_day: bool = True
    remind_1_hour: bool = True
    channel_push: bool = True
    channel_email: bool = True
    channel_sms: bool = False


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{customer_id}")
async def get_notification_prefs(
    customer_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return notification prefs for a customer. Returns defaults if not yet saved."""
    org_id = _org_id(ctx)
    try:
        pref = await db.scalar(
            select(CustomerNotificationPref).where(
                CustomerNotificationPref.org_id == org_id,
                CustomerNotificationPref.customer_id == customer_id,
            )
        )
        if not pref:
            return _default_pref(org_id, customer_id)
        return _pref_out(pref)
    except Exception as e:
        log.error("get_notification_prefs failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{customer_id}")
async def upsert_notification_prefs(
    customer_id: uuid.UUID,
    body: NotificationPrefIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create or update notification preferences for a customer."""
    org_id = _org_id(ctx)
    try:
        stmt = (
            pg_insert(CustomerNotificationPref)
            .values(
                id=uuid.uuid4(),
                org_id=org_id,
                customer_id=customer_id,
                remind_1_day=body.remind_1_day,
                remind_1_hour=body.remind_1_hour,
                channel_push=body.channel_push,
                channel_email=body.channel_email,
                channel_sms=body.channel_sms,
            )
            .on_conflict_do_update(
                constraint="uq_customer_notification_prefs_org_customer",
                set_={
                    "remind_1_day": body.remind_1_day,
                    "remind_1_hour": body.remind_1_hour,
                    "channel_push": body.channel_push,
                    "channel_email": body.channel_email,
                    "channel_sms": body.channel_sms,
                },
            )
        )
        await db.execute(stmt)
        await db.commit()

        pref = await db.scalar(
            select(CustomerNotificationPref).where(
                CustomerNotificationPref.org_id == org_id,
                CustomerNotificationPref.customer_id == customer_id,
            )
        )
        return _pref_out(pref)  # type: ignore[arg-type]
    except Exception as e:
        log.error("upsert_notification_prefs failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("")
async def list_notification_prefs(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all saved notification prefs for the org (admin view)."""
    org_id = _org_id(ctx)
    try:
        prefs = (await db.execute(
            select(CustomerNotificationPref)
            .where(CustomerNotificationPref.org_id == org_id)
            .order_by(CustomerNotificationPref.created_at)
        )).scalars().all()
        return [_pref_out(p) for p in prefs]
    except Exception as e:
        log.error("list_notification_prefs failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
