"""Booking capacity router (Sprint 11) — prefix /api/booking-capacity."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.booking_slots_config import BookingSlotsConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/booking-capacity", tags=["booking-capacity"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class CapacityOut(BaseModel):
    id: Optional[uuid.UUID]
    org_id: uuid.UUID
    service_id: Optional[uuid.UUID]
    staff_id: Optional[uuid.UUID]
    period_type: str
    total_slots: int
    booked: int
    remaining: int
    show_urgency: bool
    show_urgency_below: int


class UpsertCapacityIn(BaseModel):
    service_id: Optional[uuid.UUID] = None
    staff_id: Optional[uuid.UUID] = None
    period_type: str = Field(default="week", max_length=10)
    total_slots: int = Field(default=20, ge=1)
    show_urgency_below: int = Field(default=5, ge=0)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


async def _count_upcoming_appointments(
    db: AsyncSession,
    org_id: uuid.UUID,
    service_id: Optional[uuid.UUID],
    staff_id: Optional[uuid.UUID],
) -> int:
    """Count appointments in the next 7 days matching the given filters."""
    try:
        from app.models.bookings import Appointment
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=7)
        q = select(func.count()).select_from(Appointment).where(
            Appointment.org_id == org_id,
            Appointment.start_time >= now,
            Appointment.start_time <= cutoff,
        )
        if service_id:
            q = q.where(Appointment.service_id == service_id)
        if staff_id:
            q = q.where(Appointment.staff_id == staff_id)
        result = await db.execute(q)
        return result.scalar_one() or 0
    except Exception:
        return 0


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=CapacityOut)
async def get_booking_capacity(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    service_id: Optional[uuid.UUID] = Query(default=None),
    staff_id: Optional[uuid.UUID] = Query(default=None),
):
    try:
        org_id = _org_id(ctx)
        q = select(BookingSlotsConfig).where(BookingSlotsConfig.org_id == org_id)
        if service_id:
            q = q.where(BookingSlotsConfig.service_id == service_id)
        else:
            q = q.where(BookingSlotsConfig.service_id.is_(None))
        if staff_id:
            q = q.where(BookingSlotsConfig.staff_id == staff_id)
        else:
            q = q.where(BookingSlotsConfig.staff_id.is_(None))
        config = (await db.execute(q)).scalars().first()

        total_slots = config.total_slots if config else 20
        show_urgency_below = config.show_urgency_below if config else 5
        period_type = config.period_type if config else "week"

        booked = await _count_upcoming_appointments(db, org_id, service_id, staff_id)
        remaining = max(0, total_slots - booked)

        return CapacityOut(
            id=config.id if config else None,
            org_id=org_id,
            service_id=service_id,
            staff_id=staff_id,
            period_type=period_type,
            total_slots=total_slots,
            booked=booked,
            remaining=remaining,
            show_urgency=remaining <= show_urgency_below,
            show_urgency_below=show_urgency_below,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_booking_capacity failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("", response_model=CapacityOut)
async def upsert_booking_capacity(
    body: UpsertCapacityIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        stmt = (
            pg_insert(BookingSlotsConfig)
            .values(
                org_id=org_id,
                service_id=body.service_id,
                staff_id=body.staff_id,
                period_type=body.period_type,
                total_slots=body.total_slots,
                show_urgency_below=body.show_urgency_below,
            )
            .on_conflict_do_update(
                constraint="uq_booking_slots_config_org_service_staff_period",
                set_={
                    "total_slots": body.total_slots,
                    "show_urgency_below": body.show_urgency_below,
                    "period_type": body.period_type,
                    "updated_at": datetime.now(timezone.utc),
                },
            )
            .returning(BookingSlotsConfig)
        )
        result = await db.execute(stmt)
        await db.commit()
        config = result.scalars().first()
        if config is None:
            await db.refresh(config)

        booked = await _count_upcoming_appointments(db, org_id, body.service_id, body.staff_id)
        remaining = max(0, body.total_slots - booked)

        return CapacityOut(
            id=config.id if config else None,
            org_id=org_id,
            service_id=body.service_id,
            staff_id=body.staff_id,
            period_type=body.period_type,
            total_slots=body.total_slots,
            booked=booked,
            remaining=remaining,
            show_urgency=remaining <= body.show_urgency_below,
            show_urgency_below=body.show_urgency_below,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"upsert_booking_capacity failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{config_id}", status_code=204)
async def delete_booking_capacity(
    config_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        config = await db.get(BookingSlotsConfig, config_id)
        if not config or config.org_id != org_id:
            raise HTTPException(status_code=404, detail="Config not found")
        await db.delete(config)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_booking_capacity failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
