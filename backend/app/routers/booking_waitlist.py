"""Booking waitlist router — first-come-first-served queue for service slots.

Endpoints
─────────
GET    /api/waitlist                        → list (filter status, service_id)
POST   /api/waitlist                        → join waitlist
GET    /api/waitlist/service/{service_id}   → list for service (ordered by position)
GET    /api/waitlist/{id}                   → detail
PATCH  /api/waitlist/{id}                   → update status/notes
DELETE /api/waitlist/{id}                   → remove from waitlist
POST   /api/waitlist/{id}/notify            → mark offered
POST   /api/waitlist/{id}/book              → confirm offer → booked

NOTE: /service/{service_id} is declared BEFORE /{id} to avoid routing conflict.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.booking_waitlist import BookingWaitlistEntry

router = APIRouter(prefix="/api/waitlist", tags=["booking-waitlist"], dependencies=[Depends(require_module("invoicing"))])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _entry_out(e: BookingWaitlistEntry) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "org_id": str(e.org_id),
        "customer_id": str(e.customer_id),
        "service_id": str(e.service_id) if e.service_id else None,
        "staff_id": str(e.staff_id) if e.staff_id else None,
        "preferred_date": e.preferred_date.isoformat() if e.preferred_date else None,
        "preferred_time_from": e.preferred_time_from,
        "preferred_time_to": e.preferred_time_to,
        "flexibility_days": e.flexibility_days,
        "status": e.status,
        "notified_at": e.notified_at.isoformat() if e.notified_at else None,
        "offer_expires_at": e.offer_expires_at.isoformat() if e.offer_expires_at else None,
        "offered_appointment_id": (
            str(e.offered_appointment_id) if e.offered_appointment_id else None
        ),
        "notes": e.notes,
        "created_at": e.created_at.isoformat(),
        "updated_at": e.updated_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class WaitlistEntryIn(BaseModel):
    customer_id: uuid.UUID
    service_id: Optional[uuid.UUID] = None
    staff_id: Optional[uuid.UUID] = None
    preferred_date: Optional[date] = None
    preferred_time_from: Optional[str] = Field(default=None, max_length=8)
    preferred_time_to: Optional[str] = Field(default=None, max_length=8)
    flexibility_days: int = Field(default=0, ge=0)
    notes: Optional[str] = None


class WaitlistEntryPatch(BaseModel):
    status: Optional[str] = Field(default=None, max_length=20)
    notes: Optional[str] = None


class NotifyIn(BaseModel):
    offered_appointment_id: Optional[uuid.UUID] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_waitlist(
    status: Optional[str] = Query(default=None),
    service_id: Optional[uuid.UUID] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = (
            select(BookingWaitlistEntry)
            .where(BookingWaitlistEntry.org_id == org_id)
        )
        if status:
            q = q.where(BookingWaitlistEntry.status == status)
        if service_id:
            q = q.where(BookingWaitlistEntry.service_id == service_id)
        q = q.order_by(BookingWaitlistEntry.created_at)
        entries = (await db.execute(q)).scalars().all()
        return [_entry_out(e) for e in entries]
    except Exception as e:
        log.error("list_waitlist failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def join_waitlist(
    body: WaitlistEntryIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        entry = BookingWaitlistEntry(
            org_id=org_id,
            customer_id=body.customer_id,
            service_id=body.service_id,
            staff_id=body.staff_id,
            preferred_date=body.preferred_date,
            preferred_time_from=body.preferred_time_from,
            preferred_time_to=body.preferred_time_to,
            flexibility_days=body.flexibility_days,
            notes=body.notes,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return _entry_out(entry)
    except HTTPException:
        raise
    except Exception as e:
        log.error("join_waitlist failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# Declared before /{entry_id} to avoid routing conflict
@router.get("/service/{service_id}")
async def list_waitlist_for_service(
    service_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        entries = (await db.execute(
            select(BookingWaitlistEntry)
            .where(
                BookingWaitlistEntry.org_id == org_id,
                BookingWaitlistEntry.service_id == service_id,
            )
            .order_by(BookingWaitlistEntry.created_at)
        )).scalars().all()
        return [_entry_out(e) for e in entries]
    except Exception as e:
        log.error("list_waitlist_for_service failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{entry_id}")
async def get_waitlist_entry(
    entry_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        entry = await db.scalar(
            select(BookingWaitlistEntry).where(
                BookingWaitlistEntry.id == entry_id,
                BookingWaitlistEntry.org_id == org_id,
            )
        )
        if not entry:
            raise HTTPException(status_code=404, detail="Waitlist entry not found")
        return _entry_out(entry)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_waitlist_entry failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{entry_id}")
async def update_waitlist_entry(
    entry_id: uuid.UUID,
    body: WaitlistEntryPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        entry = await db.scalar(
            select(BookingWaitlistEntry).where(
                BookingWaitlistEntry.id == entry_id,
                BookingWaitlistEntry.org_id == org_id,
            )
        )
        if not entry:
            raise HTTPException(status_code=404, detail="Waitlist entry not found")

        if body.status is not None:
            entry.status = body.status
        if body.notes is not None:
            entry.notes = body.notes

        await db.commit()
        await db.refresh(entry)
        return _entry_out(entry)
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_waitlist_entry failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{entry_id}", status_code=204)
async def remove_from_waitlist(
    entry_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        entry = await db.scalar(
            select(BookingWaitlistEntry).where(
                BookingWaitlistEntry.id == entry_id,
                BookingWaitlistEntry.org_id == org_id,
            )
        )
        if not entry:
            raise HTTPException(status_code=404, detail="Waitlist entry not found")
        await db.delete(entry)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("remove_from_waitlist failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{entry_id}/notify")
async def notify_waitlist_entry(
    entry_id: uuid.UUID,
    body: NotifyIn = NotifyIn(),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        entry = await db.scalar(
            select(BookingWaitlistEntry).where(
                BookingWaitlistEntry.id == entry_id,
                BookingWaitlistEntry.org_id == org_id,
            )
        )
        if not entry:
            raise HTTPException(status_code=404, detail="Waitlist entry not found")

        now = datetime.now(timezone.utc)
        entry.notified_at = now
        entry.status = "offered"
        entry.offer_expires_at = now + timedelta(hours=24)
        if body.offered_appointment_id is not None:
            entry.offered_appointment_id = body.offered_appointment_id

        await db.commit()
        await db.refresh(entry)
        return _entry_out(entry)
    except HTTPException:
        raise
    except Exception as e:
        log.error("notify_waitlist_entry failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{entry_id}/book")
async def book_waitlist_offer(
    entry_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        entry = await db.scalar(
            select(BookingWaitlistEntry).where(
                BookingWaitlistEntry.id == entry_id,
                BookingWaitlistEntry.org_id == org_id,
            )
        )
        if not entry:
            raise HTTPException(status_code=404, detail="Waitlist entry not found")
        if entry.status != "offered":
            raise HTTPException(
                status_code=409,
                detail="Entry is not in offered status",
            )
        now = datetime.now(timezone.utc)
        if entry.offer_expires_at and now > entry.offer_expires_at:
            raise HTTPException(
                status_code=409,
                detail="Offer has expired",
            )

        entry.status = "booked"
        await db.commit()
        await db.refresh(entry)
        return _entry_out(entry)
    except HTTPException:
        raise
    except Exception as e:
        log.error("book_waitlist_offer failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
