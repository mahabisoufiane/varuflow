"""Lock-screen alerts router — Sprint 15.  prefix /api/lock-screen-alerts"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.lock_screen_alert import LockScreenAlert
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lock-screen-alerts", tags=["lock-screen-alerts"], dependencies=[Depends(require_module("pos"))])


def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.user_id


# ── Schemas ────────────────────────────────────────────────────────────────────

class AlertOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    user_id: uuid.UUID
    alert_type: str
    title: str
    message: str
    severity: str
    deep_link: Optional[str]
    reference_id: Optional[uuid.UUID]
    reference_type: Optional[str]
    is_dismissed: bool
    dismissed_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AlertIn(BaseModel):
    alert_type: str
    title: str
    message: str
    severity: str = "info"  # info/warning/critical
    deep_link: Optional[str] = None
    reference_id: Optional[uuid.UUID] = None
    reference_type: Optional[str] = None
    expires_at: Optional[datetime] = None


class AlertCountOut(BaseModel):
    count: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/count", response_model=AlertCountOut)
async def count_alerts(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        row = await db.execute(
            text(
                "SELECT COUNT(*) FROM lock_screen_alerts "
                "WHERE org_id = :org_id AND user_id = :user_id AND is_dismissed = false "
                "AND (expires_at IS NULL OR expires_at > NOW())"
            ),
            {"org_id": str(org_id), "user_id": str(user_id)},
        )
        return AlertCountOut(count=int(row.scalar() or 0))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"count_alerts failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=list[AlertOut])
async def list_alerts(
    severity: Optional[str] = Query(None),
    is_dismissed: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        q = select(LockScreenAlert).where(
            LockScreenAlert.org_id == org_id,
            LockScreenAlert.user_id == user_id,
            LockScreenAlert.is_dismissed.is_(is_dismissed),
        )
        if severity:
            q = q.where(LockScreenAlert.severity == severity)
        q = q.offset(skip).limit(limit)
        result = await db.execute(q)
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_alerts failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/", response_model=AlertOut, status_code=201)
async def create_alert(
    body: AlertIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        alert = LockScreenAlert(
            org_id=org_id,
            user_id=user_id,
            alert_type=body.alert_type,
            title=body.title,
            message=body.message,
            severity=body.severity,
            deep_link=body.deep_link,
            reference_id=body.reference_id,
            reference_type=body.reference_type,
            expires_at=body.expires_at,
        )
        db.add(alert)
        await db.commit()
        await db.refresh(alert)
        return alert
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_alert failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{alert_id}/dismiss", response_model=AlertOut)
async def dismiss_alert(
    alert_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        alert = await db.get(LockScreenAlert, alert_id)
        if not alert or alert.org_id != org_id or alert.user_id != user_id:
            raise HTTPException(status_code=404, detail="Alert not found")
        alert.is_dismissed = True
        alert.dismissed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(alert)
        return alert
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"dismiss_alert failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/dismiss-all", status_code=200)
async def dismiss_all_alerts(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        now = datetime.now(timezone.utc)
        result = await db.execute(
            text(
                "UPDATE lock_screen_alerts "
                "SET is_dismissed = true, dismissed_at = :now, updated_at = :now "
                "WHERE org_id = :org_id AND user_id = :user_id AND is_dismissed = false "
                "RETURNING id"
            ),
            {"org_id": str(org_id), "user_id": str(user_id), "now": now},
        )
        dismissed_count = len(result.fetchall())
        await db.commit()
        return {"dismissed": dismissed_count}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"dismiss_all_alerts failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        alert = await db.get(LockScreenAlert, alert_id)
        if not alert or alert.org_id != org_id or alert.user_id != user_id:
            raise HTTPException(status_code=404, detail="Alert not found")
        await db.delete(alert)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_alert failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
