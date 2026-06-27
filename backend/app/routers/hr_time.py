"""HR Time tracking router: billable hours per project/client."""
from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.time_entries import TimeEntry

log = logging.getLogger(__name__)
router = APIRouter()


class TimeEntryCreate(BaseModel):
    staff_id: uuid.UUID
    entry_date: date
    project: str
    client: Optional[str] = None
    description: Optional[str] = None
    hours: Decimal
    billable: bool = True
    hourly_rate: Optional[Decimal] = None


class TimeEntryUpdate(BaseModel):
    entry_date: Optional[date] = None
    project: Optional[str] = None
    client: Optional[str] = None
    description: Optional[str] = None
    hours: Optional[Decimal] = None
    billable: Optional[bool] = None
    hourly_rate: Optional[Decimal] = None


def _row(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


@router.get("/api/hr/time-entries")
async def list_time_entries(
    staff_id: Optional[uuid.UUID] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    project: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        q = select(TimeEntry).where(TimeEntry.org_id == org_id)
        if staff_id:
            q = q.where(TimeEntry.staff_id == staff_id)
        if from_date:
            q = q.where(TimeEntry.entry_date >= from_date)
        if to_date:
            q = q.where(TimeEntry.entry_date <= to_date)
        if project:
            q = q.where(TimeEntry.project.ilike(f"%{project}%"))
        q = q.order_by(TimeEntry.entry_date.desc()).limit(limit).offset(offset)
        rows = (await db.execute(q)).scalars().all()
        return [_row(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_time_entries failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/hr/time-entries/summary")
async def time_summary(
    staff_id: Optional[uuid.UUID] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        q = select(TimeEntry).where(TimeEntry.org_id == org_id)
        if staff_id:
            q = q.where(TimeEntry.staff_id == staff_id)
        if from_date:
            q = q.where(TimeEntry.entry_date >= from_date)
        if to_date:
            q = q.where(TimeEntry.entry_date <= to_date)
        rows = (await db.execute(q)).scalars().all()
        total_hours = sum(float(r.hours) for r in rows)
        billable_hours = sum(float(r.hours) for r in rows if r.billable)
        by_project: dict[str, float] = {}
        for r in rows:
            by_project[r.project] = by_project.get(r.project, 0) + float(r.hours)
        return {
            "total_hours": total_hours,
            "billable_hours": billable_hours,
            "by_project": by_project,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"time_summary failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/time-entries", status_code=201)
async def create_time_entry(
    body: TimeEntryCreate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = TimeEntry(id=uuid.uuid4(), org_id=org_id, **body.model_dump())
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _row(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_time_entry failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/hr/time-entries/{entry_id}")
async def update_time_entry(
    entry_id: uuid.UUID,
    body: TimeEntryUpdate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(TimeEntry).where(and_(TimeEntry.org_id == org_id, TimeEntry.id == entry_id))
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Time entry not found")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        await db.commit()
        await db.refresh(row)
        return _row(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"update_time_entry failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/hr/time-entries/{entry_id}", status_code=204)
async def delete_time_entry(
    entry_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(TimeEntry).where(and_(TimeEntry.org_id == org_id, TimeEntry.id == entry_id))
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Time entry not found")
        await db.delete(row)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"delete_time_entry failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
