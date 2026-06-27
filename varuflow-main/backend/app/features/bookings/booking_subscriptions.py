"""Booking subscriptions router — recurring weekly appointments for customers.

Endpoints
─────────
GET    /api/booking-subscriptions                       → list (filter customer_id, status)
POST   /api/booking-subscriptions                       → create
GET    /api/booking-subscriptions/{id}                  → detail
PATCH  /api/booking-subscriptions/{id}                  → update
DELETE /api/booking-subscriptions/{id}                  → delete
POST   /api/booking-subscriptions/{id}/pause            → pause
POST   /api/booking-subscriptions/{id}/resume           → resume
POST   /api/booking-subscriptions/{id}/cancel           → cancel
POST   /api/booking-subscriptions/{id}/generate-next    → create next Appointment
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from .booking_subscription import BookingSubscription
from .models import Appointment
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/booking-subscriptions", tags=["booking-subscriptions"], dependencies=[Depends(require_module("pos"))])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _compute_next_booking(sub: BookingSubscription) -> Optional[date]:
    """Return the next date on or after today matching day_of_week for weekly subs."""
    today = date.today()
    start = max(sub.starts_on, today)
    # Find next matching weekday on or after start
    days_ahead = (sub.day_of_week - start.weekday()) % 7
    next_date = start + timedelta(days=days_ahead)
    if sub.ends_on and next_date > sub.ends_on:
        return None
    return next_date


def _sub_out(s: BookingSubscription) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "org_id": str(s.org_id),
        "customer_id": str(s.customer_id),
        "service_id": str(s.service_id),
        "staff_id": str(s.staff_id) if s.staff_id else None,
        "day_of_week": s.day_of_week,
        "start_time": s.start_time,
        "duration_minutes": s.duration_minutes,
        "frequency": s.frequency,
        "status": s.status,
        "starts_on": s.starts_on.isoformat(),
        "ends_on": s.ends_on.isoformat() if s.ends_on else None,
        "last_booked_date": s.last_booked_date.isoformat() if s.last_booked_date else None,
        "next_booking_date": s.next_booking_date.isoformat() if s.next_booking_date else None,
        "notes": s.notes,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class BookingSubscriptionIn(BaseModel):
    customer_id: uuid.UUID
    service_id: uuid.UUID
    staff_id: Optional[uuid.UUID] = None
    day_of_week: int = Field(ge=0, le=6)
    start_time: str = Field(min_length=4, max_length=8)
    duration_minutes: int = Field(default=60, ge=1)
    frequency: str = Field(default="weekly", max_length=20)
    starts_on: date
    ends_on: Optional[date] = None

    @field_validator("day_of_week")
    @classmethod
    def validate_day_of_week(cls, v: int) -> int:
        if v < 0 or v > 6:
            raise ValueError("day_of_week must be between 0 (Monday) and 6 (Sunday)")
        return v


class BookingSubscriptionPatch(BaseModel):
    staff_id: Optional[uuid.UUID] = None
    day_of_week: Optional[int] = Field(default=None, ge=0, le=6)
    start_time: Optional[str] = Field(default=None, max_length=8)
    duration_minutes: Optional[int] = Field(default=None, ge=1)
    frequency: Optional[str] = Field(default=None, max_length=20)
    starts_on: Optional[date] = None
    ends_on: Optional[date] = None
    notes: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_booking_subscriptions(
    customer_id: Optional[uuid.UUID] = Query(default=None),
    status: Optional[str] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = select(BookingSubscription).where(BookingSubscription.org_id == org_id)
        if customer_id:
            q = q.where(BookingSubscription.customer_id == customer_id)
        if status:
            q = q.where(BookingSubscription.status == status)
        q = q.order_by(BookingSubscription.created_at)
        subs = (await db.execute(q)).scalars().all()
        return [_sub_out(s) for s in subs]
    except Exception as e:
        log.error("list_booking_subscriptions failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_booking_subscription(
    body: BookingSubscriptionIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        sub = BookingSubscription(
            org_id=org_id,
            customer_id=body.customer_id,
            service_id=body.service_id,
            staff_id=body.staff_id,
            day_of_week=body.day_of_week,
            start_time=body.start_time,
            duration_minutes=body.duration_minutes,
            frequency=body.frequency,
            starts_on=body.starts_on,
            ends_on=body.ends_on,
        )
        sub.next_booking_date = _compute_next_booking(sub)
        db.add(sub)
        await db.commit()
        await db.refresh(sub)
        return _sub_out(sub)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_booking_subscription failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{sub_id}")
async def get_booking_subscription(
    sub_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        sub = await db.scalar(
            select(BookingSubscription).where(
                BookingSubscription.id == sub_id,
                BookingSubscription.org_id == org_id,
            )
        )
        if not sub:
            raise HTTPException(status_code=404, detail="Booking subscription not found")
        return _sub_out(sub)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_booking_subscription failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{sub_id}")
async def update_booking_subscription(
    sub_id: uuid.UUID,
    body: BookingSubscriptionPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        sub = await db.scalar(
            select(BookingSubscription).where(
                BookingSubscription.id == sub_id,
                BookingSubscription.org_id == org_id,
            )
        )
        if not sub:
            raise HTTPException(status_code=404, detail="Booking subscription not found")

        if body.staff_id is not None:
            sub.staff_id = body.staff_id
        if body.day_of_week is not None:
            sub.day_of_week = body.day_of_week
        if body.start_time is not None:
            sub.start_time = body.start_time
        if body.duration_minutes is not None:
            sub.duration_minutes = body.duration_minutes
        if body.frequency is not None:
            sub.frequency = body.frequency
        if body.starts_on is not None:
            sub.starts_on = body.starts_on
        if body.ends_on is not None:
            sub.ends_on = body.ends_on
        if body.notes is not None:
            sub.notes = body.notes

        sub.next_booking_date = _compute_next_booking(sub)

        await db.commit()
        await db.refresh(sub)
        return _sub_out(sub)
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_booking_subscription failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{sub_id}", status_code=204)
async def delete_booking_subscription(
    sub_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        sub = await db.scalar(
            select(BookingSubscription).where(
                BookingSubscription.id == sub_id,
                BookingSubscription.org_id == org_id,
            )
        )
        if not sub:
            raise HTTPException(status_code=404, detail="Booking subscription not found")
        await db.delete(sub)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_booking_subscription failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{sub_id}/pause")
async def pause_booking_subscription(
    sub_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        sub = await db.scalar(
            select(BookingSubscription).where(
                BookingSubscription.id == sub_id,
                BookingSubscription.org_id == org_id,
            )
        )
        if not sub:
            raise HTTPException(status_code=404, detail="Booking subscription not found")
        sub.status = "paused"
        await db.commit()
        await db.refresh(sub)
        return _sub_out(sub)
    except HTTPException:
        raise
    except Exception as e:
        log.error("pause_booking_subscription failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{sub_id}/resume")
async def resume_booking_subscription(
    sub_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        sub = await db.scalar(
            select(BookingSubscription).where(
                BookingSubscription.id == sub_id,
                BookingSubscription.org_id == org_id,
            )
        )
        if not sub:
            raise HTTPException(status_code=404, detail="Booking subscription not found")
        sub.status = "active"
        sub.next_booking_date = _compute_next_booking(sub)
        await db.commit()
        await db.refresh(sub)
        return _sub_out(sub)
    except HTTPException:
        raise
    except Exception as e:
        log.error("resume_booking_subscription failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{sub_id}/cancel")
async def cancel_booking_subscription(
    sub_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        sub = await db.scalar(
            select(BookingSubscription).where(
                BookingSubscription.id == sub_id,
                BookingSubscription.org_id == org_id,
            )
        )
        if not sub:
            raise HTTPException(status_code=404, detail="Booking subscription not found")
        sub.status = "cancelled"
        await db.commit()
        await db.refresh(sub)
        return _sub_out(sub)
    except HTTPException:
        raise
    except Exception as e:
        log.error("cancel_booking_subscription failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{sub_id}/generate-next", status_code=201)
async def generate_next_appointment(
    sub_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        sub = await db.scalar(
            select(BookingSubscription).where(
                BookingSubscription.id == sub_id,
                BookingSubscription.org_id == org_id,
            )
        )
        if not sub:
            raise HTTPException(status_code=404, detail="Booking subscription not found")
        if not sub.next_booking_date:
            raise HTTPException(
                status_code=422, detail="No next booking date available for this subscription"
            )

        # Combine next_booking_date + start_time string into a timezone-aware datetime
        h, m = (int(p) for p in sub.start_time.split(":"))
        start_dt = datetime(
            sub.next_booking_date.year,
            sub.next_booking_date.month,
            sub.next_booking_date.day,
            h, m, tzinfo=timezone.utc,
        )

        appointment = Appointment(
            org_id=org_id,
            customer_id=sub.customer_id,
            service_id=sub.service_id,
            staff_id=sub.staff_id,
            start_time=start_dt,
            duration_minutes=sub.duration_minutes,
            status="scheduled",
            notes=sub.notes,
        )
        db.add(appointment)
        await db.flush()

        # Update subscription tracking
        sub.last_booked_date = sub.next_booking_date
        sub.next_booking_date = _compute_next_booking(sub)

        await db.commit()
        await db.refresh(appointment)

        return {
            "id": str(appointment.id),
            "org_id": str(appointment.org_id),
            "customer_id": str(appointment.customer_id) if appointment.customer_id else None,
            "service_id": str(appointment.service_id),
            "staff_id": str(appointment.staff_id) if appointment.staff_id else None,
            "start_time": appointment.start_time.isoformat(),
            "duration_minutes": appointment.duration_minutes,
            "status": appointment.status,
            "notes": appointment.notes,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("generate_next_appointment failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
