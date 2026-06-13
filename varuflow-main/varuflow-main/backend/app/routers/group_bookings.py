"""Group bookings router — one appointment for a party with optional split payment.

Endpoints
─────────
GET    /api/group-bookings                              → list (filter status)
POST   /api/group-bookings                              → create with participants
GET    /api/group-bookings/{id}                         → detail with participants
PATCH  /api/group-bookings/{id}                         → update status/notes/appointment_id
DELETE /api/group-bookings/{id}                         → delete if pending
POST   /api/group-bookings/{id}/confirm                 → confirm
POST   /api/group-bookings/{id}/cancel                  → cancel
PATCH  /api/group-bookings/{id}/participants/{pid}      → mark paid or update amount
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.group_booking import GroupBooking, GroupBookingParticipant

router = APIRouter(prefix="/api/group-bookings", tags=["group-bookings"])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _participant_out(p: GroupBookingParticipant) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "group_booking_id": str(p.group_booking_id),
        "customer_id": str(p.customer_id) if p.customer_id else None,
        "name": p.name,
        "email": p.email,
        "amount_due": float(p.amount_due) if p.amount_due is not None else None,
        "paid": p.paid,
        "paid_at": p.paid_at.isoformat() if p.paid_at else None,
    }


def _booking_out(b: GroupBooking, participants: list[GroupBookingParticipant]) -> dict[str, Any]:
    return {
        "id": str(b.id),
        "org_id": str(b.org_id),
        "lead_customer_id": str(b.lead_customer_id),
        "service_id": str(b.service_id),
        "appointment_id": str(b.appointment_id) if b.appointment_id else None,
        "title": b.title,
        "party_size": b.party_size,
        "status": b.status,
        "split_payment": b.split_payment,
        "total_amount": float(b.total_amount) if b.total_amount is not None else None,
        "currency": b.currency,
        "notes": b.notes,
        "created_at": b.created_at.isoformat(),
        "participants": [_participant_out(p) for p in participants],
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class ParticipantIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: Optional[str] = Field(default=None, max_length=320)
    amount_due: Optional[Decimal] = None


class GroupBookingIn(BaseModel):
    lead_customer_id: uuid.UUID
    service_id: uuid.UUID
    title: Optional[str] = Field(default=None, max_length=300)
    party_size: int = Field(ge=1)
    split_payment: bool = False
    total_amount: Optional[Decimal] = None
    currency: str = Field(default="SEK", max_length=3)
    notes: Optional[str] = None
    participants: list[ParticipantIn] = Field(default_factory=list)


class GroupBookingPatch(BaseModel):
    status: Optional[str] = Field(default=None, max_length=20)
    notes: Optional[str] = None
    appointment_id: Optional[uuid.UUID] = None


class ParticipantPatch(BaseModel):
    paid: Optional[bool] = None
    amount_due: Optional[Decimal] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_group_bookings(
    status: Optional[str] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = select(GroupBooking).where(GroupBooking.org_id == org_id)
        if status:
            q = q.where(GroupBooking.status == status)
        q = q.order_by(GroupBooking.created_at)
        bookings = (await db.execute(q)).scalars().all()

        results = []
        for b in bookings:
            parts = (await db.execute(
                select(GroupBookingParticipant)
                .where(GroupBookingParticipant.group_booking_id == b.id)
            )).scalars().all()
            results.append(_booking_out(b, list(parts)))
        return results
    except Exception as e:
        log.error("list_group_bookings failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_group_booking(
    body: GroupBookingIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        booking = GroupBooking(
            org_id=org_id,
            lead_customer_id=body.lead_customer_id,
            service_id=body.service_id,
            title=body.title,
            party_size=body.party_size,
            split_payment=body.split_payment,
            total_amount=body.total_amount,
            currency=body.currency,
            notes=body.notes,
        )
        db.add(booking)
        await db.flush()

        # Auto-divide amount if split_payment and total_amount are set
        auto_amount: Optional[Decimal] = None
        if body.split_payment and body.total_amount and body.party_size > 0:
            auto_amount = body.total_amount / Decimal(str(body.party_size))

        participants: list[GroupBookingParticipant] = []
        for p_in in body.participants:
            amount = p_in.amount_due if p_in.amount_due is not None else auto_amount
            p = GroupBookingParticipant(
                group_booking_id=booking.id,
                name=p_in.name,
                email=p_in.email,
                amount_due=amount,
            )
            db.add(p)
            participants.append(p)

        await db.commit()
        await db.refresh(booking)
        for p in participants:
            await db.refresh(p)

        return _booking_out(booking, participants)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_group_booking failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{booking_id}")
async def get_group_booking(
    booking_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        booking = await db.scalar(
            select(GroupBooking).where(
                GroupBooking.id == booking_id, GroupBooking.org_id == org_id
            )
        )
        if not booking:
            raise HTTPException(status_code=404, detail="Group booking not found")

        parts = (await db.execute(
            select(GroupBookingParticipant)
            .where(GroupBookingParticipant.group_booking_id == booking_id)
        )).scalars().all()

        return _booking_out(booking, list(parts))
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_group_booking failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{booking_id}")
async def update_group_booking(
    booking_id: uuid.UUID,
    body: GroupBookingPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        booking = await db.scalar(
            select(GroupBooking).where(
                GroupBooking.id == booking_id, GroupBooking.org_id == org_id
            )
        )
        if not booking:
            raise HTTPException(status_code=404, detail="Group booking not found")

        if body.status is not None:
            booking.status = body.status
        if body.notes is not None:
            booking.notes = body.notes
        if body.appointment_id is not None:
            booking.appointment_id = body.appointment_id

        await db.commit()
        await db.refresh(booking)

        parts = (await db.execute(
            select(GroupBookingParticipant)
            .where(GroupBookingParticipant.group_booking_id == booking_id)
        )).scalars().all()

        return _booking_out(booking, list(parts))
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_group_booking failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{booking_id}", status_code=204)
async def delete_group_booking(
    booking_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        booking = await db.scalar(
            select(GroupBooking).where(
                GroupBooking.id == booking_id, GroupBooking.org_id == org_id
            )
        )
        if not booking:
            raise HTTPException(status_code=404, detail="Group booking not found")
        if booking.status != "pending":
            raise HTTPException(
                status_code=422,
                detail="Only pending group bookings can be deleted",
            )
        await db.delete(booking)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_group_booking failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{booking_id}/confirm")
async def confirm_group_booking(
    booking_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        booking = await db.scalar(
            select(GroupBooking).where(
                GroupBooking.id == booking_id, GroupBooking.org_id == org_id
            )
        )
        if not booking:
            raise HTTPException(status_code=404, detail="Group booking not found")
        booking.status = "confirmed"
        await db.commit()
        await db.refresh(booking)

        parts = (await db.execute(
            select(GroupBookingParticipant)
            .where(GroupBookingParticipant.group_booking_id == booking_id)
        )).scalars().all()
        return _booking_out(booking, list(parts))
    except HTTPException:
        raise
    except Exception as e:
        log.error("confirm_group_booking failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{booking_id}/cancel")
async def cancel_group_booking(
    booking_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        booking = await db.scalar(
            select(GroupBooking).where(
                GroupBooking.id == booking_id, GroupBooking.org_id == org_id
            )
        )
        if not booking:
            raise HTTPException(status_code=404, detail="Group booking not found")
        booking.status = "cancelled"
        await db.commit()
        await db.refresh(booking)

        parts = (await db.execute(
            select(GroupBookingParticipant)
            .where(GroupBookingParticipant.group_booking_id == booking_id)
        )).scalars().all()
        return _booking_out(booking, list(parts))
    except HTTPException:
        raise
    except Exception as e:
        log.error("cancel_group_booking failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{booking_id}/participants/{participant_id}")
async def update_group_booking_participant(
    booking_id: uuid.UUID,
    participant_id: uuid.UUID,
    body: ParticipantPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        # Verify group booking belongs to org
        booking = await db.scalar(
            select(GroupBooking).where(
                GroupBooking.id == booking_id, GroupBooking.org_id == org_id
            )
        )
        if not booking:
            raise HTTPException(status_code=404, detail="Group booking not found")

        participant = await db.scalar(
            select(GroupBookingParticipant).where(
                GroupBookingParticipant.id == participant_id,
                GroupBookingParticipant.group_booking_id == booking_id,
            )
        )
        if not participant:
            raise HTTPException(status_code=404, detail="Participant not found")

        if body.paid is not None:
            participant.paid = body.paid
            if body.paid:
                participant.paid_at = datetime.now(timezone.utc)
        if body.amount_due is not None:
            participant.amount_due = body.amount_due

        await db.commit()
        await db.refresh(participant)
        return _participant_out(participant)
    except HTTPException:
        raise
    except Exception as e:
        log.error(
            "update_group_booking_participant failed: %s", e,
            extra={"org_id": str(org_id)},
        )
        raise HTTPException(status_code=500, detail="Internal server error")
