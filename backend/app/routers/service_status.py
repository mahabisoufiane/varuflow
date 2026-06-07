"""Service Status Alerts — push notification records for appointment status changes.

Endpoints
─────────
GET    /api/service-status/alerts                       → list alerts for org
POST   /api/service-status/alerts                       → create + send alert
GET    /api/service-status/appointment/{appointment_id} → all alerts for appointment
GET    /api/service-status/alerts/{id}                  → detail
DELETE /api/service-status/alerts/{id}                  → delete
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
from app.models.service_status_alert import ServiceStatusAlert
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/service-status", tags=["service-status"], dependencies=[Depends(require_module("pos"))])
log = logging.getLogger(__name__)

_VALID_ALERT_TYPES = {
    "running_late", "cancelled", "rescheduled", "ready", "completed", "custom"
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    user, _ = ctx
    return uuid.UUID(str(user["user_id"]))


def _alert_out(a: ServiceStatusAlert) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "org_id": str(a.org_id),
        "appointment_id": str(a.appointment_id) if a.appointment_id else None,
        "customer_id": str(a.customer_id) if a.customer_id else None,
        "staff_user_id": str(a.staff_user_id) if a.staff_user_id else None,
        "alert_type": a.alert_type,
        "delay_minutes": a.delay_minutes,
        "message": a.message,
        "push_sent": a.push_sent,
        "push_sent_at": a.push_sent_at.isoformat() if a.push_sent_at else None,
        "created_at": a.created_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class AlertIn(BaseModel):
    appointment_id: Optional[uuid.UUID] = None
    customer_id: Optional[uuid.UUID] = None
    alert_type: str = Field(min_length=1, max_length=50)
    delay_minutes: Optional[int] = None
    message: str = Field(min_length=1)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/alerts")
async def list_alerts(
    appointment_id: Optional[uuid.UUID] = Query(default=None),
    alert_type: Optional[str] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = select(ServiceStatusAlert).where(ServiceStatusAlert.org_id == org_id)
        if appointment_id:
            q = q.where(ServiceStatusAlert.appointment_id == appointment_id)
        if alert_type:
            q = q.where(ServiceStatusAlert.alert_type == alert_type)
        q = q.order_by(ServiceStatusAlert.created_at.desc()).limit(100)
        alerts = (await db.execute(q)).scalars().all()
        return [_alert_out(a) for a in alerts]
    except Exception as e:
        log.error("list_alerts failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/alerts", status_code=201)
async def create_alert(
    body: AlertIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    try:
        if body.alert_type not in _VALID_ALERT_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"alert_type must be one of {sorted(_VALID_ALERT_TYPES)}",
            )
        if body.alert_type == "running_late" and body.delay_minutes is None:
            raise HTTPException(
                status_code=422,
                detail="delay_minutes is required when alert_type is running_late",
            )

        now = datetime.now(timezone.utc)
        alert = ServiceStatusAlert(
            org_id=org_id,
            appointment_id=body.appointment_id,
            customer_id=body.customer_id,
            staff_user_id=user_id,
            alert_type=body.alert_type,
            delay_minutes=body.delay_minutes,
            message=body.message,
            # Simulate push send — in production this would call the push service
            push_sent=True,
            push_sent_at=now,
        )
        db.add(alert)
        await db.commit()
        await db.refresh(alert)
        return _alert_out(alert)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_alert failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# Declare before /{id} to prevent path collision
@router.get("/appointment/{appointment_id}")
async def list_alerts_for_appointment(
    appointment_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = (
            select(ServiceStatusAlert)
            .where(
                ServiceStatusAlert.org_id == org_id,
                ServiceStatusAlert.appointment_id == appointment_id,
            )
            .order_by(ServiceStatusAlert.created_at.desc())
        )
        alerts = (await db.execute(q)).scalars().all()
        return [_alert_out(a) for a in alerts]
    except Exception as e:
        log.error(
            "list_alerts_for_appointment failed: %s", e, extra={"org_id": str(org_id)}
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/alerts/{alert_id}")
async def get_alert(
    alert_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        alert = await db.scalar(
            select(ServiceStatusAlert).where(
                ServiceStatusAlert.id == alert_id,
                ServiceStatusAlert.org_id == org_id,
            )
        )
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        return _alert_out(alert)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_alert failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/alerts/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        alert = await db.scalar(
            select(ServiceStatusAlert).where(
                ServiceStatusAlert.id == alert_id,
                ServiceStatusAlert.org_id == org_id,
            )
        )
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        await db.delete(alert)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_alert failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
