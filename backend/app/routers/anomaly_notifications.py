"""Anomaly notifications router — Sprint 13.  prefix /api/anomalies"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.anomaly_notification import AnomalyNotification

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/anomalies", tags=["anomaly-notifications"])


def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Schemas ────────────────────────────────────────────────────────────────────

class AnomalyNotificationIn(BaseModel):
    type: str
    severity: str = "info"
    title: str
    body: str
    reference_id: Optional[uuid.UUID] = None
    reference_type: Optional[str] = None


class AnomalyNotificationOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    type: str
    severity: str
    title: str
    body: str
    reference_id: Optional[uuid.UUID]
    reference_type: Optional[str]
    is_read: bool
    pushed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class UnreadCountOut(BaseModel):
    count: int
    by_severity: dict


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/unread-count", response_model=UnreadCountOut)
async def unread_count(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        q = select(
            AnomalyNotification.severity,
            func.count().label("cnt"),
        ).where(
            AnomalyNotification.org_id == org_id,
            AnomalyNotification.is_read.is_(False),
        ).group_by(AnomalyNotification.severity)
        result = await db.execute(q)
        by_severity = {"info": 0, "warning": 0, "critical": 0}
        total = 0
        for row in result.all():
            by_severity[row.severity] = row.cnt
            total += row.cnt
        return UnreadCountOut(count=total, by_severity=by_severity)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"unread_count failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=list[AnomalyNotificationOut])
async def list_anomalies(
    severity: Optional[str] = Query(None),
    is_read: Optional[bool] = Query(None),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        q = select(AnomalyNotification).where(AnomalyNotification.org_id == org_id)
        if severity:
            q = q.where(AnomalyNotification.severity == severity)
        if is_read is not None:
            q = q.where(AnomalyNotification.is_read.is_(is_read))
        q = q.order_by(AnomalyNotification.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(q)
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_anomalies failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=AnomalyNotificationOut, status_code=201)
async def create_anomaly(
    body: AnomalyNotificationIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        notif = AnomalyNotification(
            org_id=org_id,
            type=body.type,
            severity=body.severity,
            title=body.title,
            body=body.body,
            reference_id=body.reference_id,
            reference_type=body.reference_type,
        )
        db.add(notif)
        await db.commit()
        await db.refresh(notif)
        return notif
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_anomaly failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{anomaly_id}/read", response_model=AnomalyNotificationOut)
async def mark_read(
    anomaly_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        notif = await db.get(AnomalyNotification, anomaly_id)
        if not notif or notif.org_id != org_id:
            raise HTTPException(status_code=404, detail="Anomaly notification not found")
        notif.is_read = True
        await db.commit()
        await db.refresh(notif)
        return notif
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"mark_read failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/read-all", status_code=200)
async def mark_all_read(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        await db.execute(
            update(AnomalyNotification)
            .where(
                AnomalyNotification.org_id == org_id,
                AnomalyNotification.is_read.is_(False),
            )
            .values(is_read=True)
        )
        await db.commit()
        return {"detail": "All notifications marked as read"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"mark_all_read failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{anomaly_id}", status_code=204)
async def delete_anomaly(
    anomaly_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        notif = await db.get(AnomalyNotification, anomaly_id)
        if not notif or notif.org_id != org_id:
            raise HTTPException(status_code=404, detail="Anomaly notification not found")
        await db.delete(notif)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_anomaly failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
