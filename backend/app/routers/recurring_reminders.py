"""Recurring Reminders — scheduled reminders with occurrence tracking.

Endpoints
─────────
GET    /api/reminders/due                   → active reminders due within 24h
GET    /api/reminders/occurrences/{occ_id}  → (see PATCH below)
GET    /api/reminders                       → list reminders
POST   /api/reminders                       → create reminder
GET    /api/reminders/{id}                  → detail with last 10 occurrences
PATCH  /api/reminders/{id}                  → update reminder
DELETE /api/reminders/{id}                  → delete reminder
POST   /api/reminders/{id}/pause            → pause (is_active=False)
POST   /api/reminders/{id}/resume           → resume + recompute next_due_at
POST   /api/reminders/{id}/trigger          → create occurrence, update last/next
PATCH  /api/reminders/occurrences/{occ_id}  → update occurrence status/notes
"""
from __future__ import annotations

import logging
import uuid
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.recurring_reminder import RecurringReminder, ReminderOccurrence
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/reminders", tags=["reminders"], dependencies=[Depends(require_module("invoicing"))])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    user, _ = ctx
    return uuid.UUID(str(user["user_id"]))


def _compute_next_due(reminder: RecurringReminder) -> datetime:
    now = datetime.now(timezone.utc)
    h, m = map(int, reminder.time_of_day.split(":"))

    if reminder.frequency == "daily":
        return (now + timedelta(days=1)).replace(
            hour=h, minute=m, second=0, microsecond=0
        )

    if reminder.frequency == "weekly":
        # day_of_week: 0=Mon, 6=Sun
        target_dow = reminder.day_of_week if reminder.day_of_week is not None else 0
        current_dow = now.weekday()
        days_ahead = (target_dow - current_dow) % 7
        if days_ahead == 0:
            days_ahead = 7  # always schedule at least one week ahead
        return (now + timedelta(days=days_ahead)).replace(
            hour=h, minute=m, second=0, microsecond=0
        )

    if reminder.frequency == "monthly":
        target_day = reminder.day_of_month if reminder.day_of_month is not None else 1
        # Try next month first; clamp day to valid range
        year = now.year
        month = now.month + 1
        if month > 12:
            month = 1
            year += 1
        max_day = monthrange(year, month)[1]
        day = min(target_day, max_day)
        return datetime(year, month, day, h, m, 0, tzinfo=timezone.utc)

    # fallback: 1 day from now
    return (now + timedelta(days=1)).replace(
        hour=h, minute=m, second=0, microsecond=0
    )


def _reminder_out(r: RecurringReminder, occurrences: list[ReminderOccurrence] | None = None) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": str(r.id),
        "org_id": str(r.org_id),
        "created_by": str(r.created_by),
        "title": r.title,
        "description": r.description,
        "frequency": r.frequency,
        "day_of_week": r.day_of_week,
        "day_of_month": r.day_of_month,
        "time_of_day": r.time_of_day,
        "assigned_to_user_id": str(r.assigned_to_user_id) if r.assigned_to_user_id else None,
        "is_active": r.is_active,
        "last_triggered_at": r.last_triggered_at.isoformat() if r.last_triggered_at else None,
        "next_due_at": r.next_due_at.isoformat() if r.next_due_at else None,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }
    if occurrences is not None:
        d["occurrences"] = [_occ_out(o) for o in occurrences]
    return d


def _occ_out(o: ReminderOccurrence) -> dict[str, Any]:
    return {
        "id": str(o.id),
        "reminder_id": str(o.reminder_id),
        "due_at": o.due_at.isoformat(),
        "status": o.status,
        "completed_at": o.completed_at.isoformat() if o.completed_at else None,
        "notes": o.notes,
        "created_at": o.created_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class ReminderIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: Optional[str] = None
    frequency: str = Field(default="weekly")
    day_of_week: Optional[int] = Field(default=None, ge=0, le=6)
    day_of_month: Optional[int] = Field(default=None, ge=1, le=31)
    time_of_day: str = Field(default="09:00")
    assigned_to_user_id: Optional[uuid.UUID] = None
    is_active: bool = True


class ReminderPatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=300)
    description: Optional[str] = None
    frequency: Optional[str] = None
    day_of_week: Optional[int] = Field(default=None, ge=0, le=6)
    day_of_month: Optional[int] = Field(default=None, ge=1, le=31)
    time_of_day: Optional[str] = None
    assigned_to_user_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None


class OccurrencePatch(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/due")
async def list_due_reminders(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Active reminders due within the next 24 hours."""
    org_id = _org_id(ctx)
    try:
        cutoff = datetime.now(timezone.utc) + timedelta(hours=24)
        reminders = (await db.execute(
            select(RecurringReminder).where(
                RecurringReminder.org_id == org_id,
                RecurringReminder.is_active.is_(True),
                RecurringReminder.next_due_at <= cutoff,
            )
        )).scalars().all()
        return [_reminder_out(r) for r in reminders]
    except Exception as e:
        log.error("list_due_reminders failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/occurrences/{occ_id}")
async def patch_occurrence(
    occ_id: uuid.UUID,
    body: OccurrencePatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        occ = await db.scalar(
            select(ReminderOccurrence).where(ReminderOccurrence.id == occ_id)
        )
        if not occ:
            raise HTTPException(status_code=404, detail="Occurrence not found")

        # Verify org ownership via parent reminder
        reminder = await db.scalar(
            select(RecurringReminder).where(
                RecurringReminder.id == occ.reminder_id,
                RecurringReminder.org_id == org_id,
            )
        )
        if not reminder:
            raise HTTPException(status_code=403, detail="Not authorised")

        if body.status is not None:
            occ.status = body.status
        if body.notes is not None:
            occ.notes = body.notes

        await db.commit()
        await db.refresh(occ)
        return _occ_out(occ)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_occurrence failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("")
async def list_reminders(
    is_active: Optional[bool] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = select(RecurringReminder).where(RecurringReminder.org_id == org_id)
        if is_active is not None:
            q = q.where(RecurringReminder.is_active.is_(is_active))
        q = q.order_by(RecurringReminder.created_at)
        reminders = (await db.execute(q)).scalars().all()
        return [_reminder_out(r) for r in reminders]
    except Exception as e:
        log.error("list_reminders failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_reminder(
    body: ReminderIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    try:
        reminder = RecurringReminder(
            org_id=org_id,
            created_by=user_id,
            title=body.title,
            description=body.description,
            frequency=body.frequency,
            day_of_week=body.day_of_week,
            day_of_month=body.day_of_month,
            time_of_day=body.time_of_day,
            assigned_to_user_id=body.assigned_to_user_id,
            is_active=body.is_active,
        )
        reminder.next_due_at = _compute_next_due(reminder)
        db.add(reminder)
        await db.commit()
        await db.refresh(reminder)
        return _reminder_out(reminder)
    except Exception as e:
        log.error("create_reminder failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{reminder_id}")
async def get_reminder(
    reminder_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        reminder = await db.scalar(
            select(RecurringReminder).where(
                RecurringReminder.id == reminder_id,
                RecurringReminder.org_id == org_id,
            )
        )
        if not reminder:
            raise HTTPException(status_code=404, detail="Reminder not found")

        occs = (await db.execute(
            select(ReminderOccurrence)
            .where(ReminderOccurrence.reminder_id == reminder_id)
            .order_by(ReminderOccurrence.due_at.desc())
            .limit(10)
        )).scalars().all()

        return _reminder_out(reminder, occurrences=occs)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_reminder failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{reminder_id}")
async def patch_reminder(
    reminder_id: uuid.UUID,
    body: ReminderPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        reminder = await db.scalar(
            select(RecurringReminder).where(
                RecurringReminder.id == reminder_id,
                RecurringReminder.org_id == org_id,
            )
        )
        if not reminder:
            raise HTTPException(status_code=404, detail="Reminder not found")

        if body.title is not None:
            reminder.title = body.title
        if body.description is not None:
            reminder.description = body.description
        if body.frequency is not None:
            reminder.frequency = body.frequency
        if body.day_of_week is not None:
            reminder.day_of_week = body.day_of_week
        if body.day_of_month is not None:
            reminder.day_of_month = body.day_of_month
        if body.time_of_day is not None:
            reminder.time_of_day = body.time_of_day
        if body.assigned_to_user_id is not None:
            reminder.assigned_to_user_id = body.assigned_to_user_id
        if body.is_active is not None:
            reminder.is_active = body.is_active

        reminder.next_due_at = _compute_next_due(reminder)
        reminder.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(reminder)
        return _reminder_out(reminder)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_reminder failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{reminder_id}", status_code=204)
async def delete_reminder(
    reminder_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        reminder = await db.scalar(
            select(RecurringReminder).where(
                RecurringReminder.id == reminder_id,
                RecurringReminder.org_id == org_id,
            )
        )
        if not reminder:
            raise HTTPException(status_code=404, detail="Reminder not found")
        await db.delete(reminder)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_reminder failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{reminder_id}/pause")
async def pause_reminder(
    reminder_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        reminder = await db.scalar(
            select(RecurringReminder).where(
                RecurringReminder.id == reminder_id,
                RecurringReminder.org_id == org_id,
            )
        )
        if not reminder:
            raise HTTPException(status_code=404, detail="Reminder not found")
        reminder.is_active = False
        reminder.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(reminder)
        return _reminder_out(reminder)
    except HTTPException:
        raise
    except Exception as e:
        log.error("pause_reminder failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{reminder_id}/resume")
async def resume_reminder(
    reminder_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        reminder = await db.scalar(
            select(RecurringReminder).where(
                RecurringReminder.id == reminder_id,
                RecurringReminder.org_id == org_id,
            )
        )
        if not reminder:
            raise HTTPException(status_code=404, detail="Reminder not found")
        reminder.is_active = True
        reminder.next_due_at = _compute_next_due(reminder)
        reminder.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(reminder)
        return _reminder_out(reminder)
    except HTTPException:
        raise
    except Exception as e:
        log.error("resume_reminder failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{reminder_id}/trigger", status_code=201)
async def trigger_reminder(
    reminder_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        reminder = await db.scalar(
            select(RecurringReminder).where(
                RecurringReminder.id == reminder_id,
                RecurringReminder.org_id == org_id,
            )
        )
        if not reminder:
            raise HTTPException(status_code=404, detail="Reminder not found")

        now = datetime.now(timezone.utc)
        occ = ReminderOccurrence(
            reminder_id=reminder_id,
            due_at=now,
            status="pending",
        )
        db.add(occ)

        reminder.last_triggered_at = now
        reminder.next_due_at = _compute_next_due(reminder)
        reminder.updated_at = now

        await db.commit()
        await db.refresh(occ)
        return _occ_out(occ)
    except HTTPException:
        raise
    except Exception as e:
        log.error("trigger_reminder failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
