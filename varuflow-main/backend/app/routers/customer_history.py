"""Customer History — unified timeline of all customer interactions.

Endpoints
─────────
DELETE /api/history/events/{event_id}          → delete a manual event
GET    /api/history/{customer_id}              → list events (paginated)
POST   /api/history/{customer_id}              → log manual event
GET    /api/history/{customer_id}/summary      → aggregated stats
POST   /api/history/{customer_id}/backfill     → auto-populate from existing data
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.bookings import Appointment
from app.models.customer_history import CustomerHistoryEvent
from app.models.invoicing import Invoice, Payment

router = APIRouter(prefix="/api/history", tags=["customer-history"])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _event_out(e: CustomerHistoryEvent) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "org_id": str(e.org_id),
        "customer_id": str(e.customer_id),
        "event_type": e.event_type,
        "event_date": e.event_date.isoformat(),
        "title": e.title,
        "description": e.description,
        "reference_id": str(e.reference_id) if e.reference_id else None,
        "reference_type": e.reference_type,
        "amount": float(e.amount) if e.amount is not None else None,
        "currency": e.currency,
        "created_at": e.created_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class HistoryEventIn(BaseModel):
    event_type: str = Field(min_length=1, max_length=50)
    event_date: Optional[datetime] = None
    title: str = Field(min_length=1, max_length=300)
    description: Optional[str] = None
    reference_id: Optional[uuid.UUID] = None
    reference_type: Optional[str] = Field(default=None, max_length=50)
    amount: Optional[Decimal] = None
    currency: Optional[str] = Field(default=None, max_length=3)


# ── Endpoints ─────────────────────────────────────────────────────────────────

# Declare BEFORE /{customer_id} to prevent path collision
@router.delete("/events/{event_id}", status_code=204)
async def delete_event(
    event_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        event = await db.scalar(
            select(CustomerHistoryEvent).where(
                CustomerHistoryEvent.id == event_id,
                CustomerHistoryEvent.org_id == org_id,
            )
        )
        if not event:
            raise HTTPException(status_code=404, detail="History event not found")
        await db.delete(event)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_event failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{customer_id}")
async def list_events(
    customer_id: uuid.UUID,
    event_type: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = select(CustomerHistoryEvent).where(
            CustomerHistoryEvent.org_id == org_id,
            CustomerHistoryEvent.customer_id == customer_id,
        )
        if event_type:
            q = q.where(CustomerHistoryEvent.event_type == event_type)
        q = q.order_by(CustomerHistoryEvent.event_date.desc()).limit(limit).offset(offset)
        events = (await db.execute(q)).scalars().all()
        return [_event_out(e) for e in events]
    except Exception as e:
        log.error("list_events failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{customer_id}", status_code=201)
async def log_event(
    customer_id: uuid.UUID,
    body: HistoryEventIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        event = CustomerHistoryEvent(
            org_id=org_id,
            customer_id=customer_id,
            event_type=body.event_type,
            event_date=body.event_date or datetime.now(timezone.utc),
            title=body.title,
            description=body.description,
            reference_id=body.reference_id,
            reference_type=body.reference_type,
            amount=body.amount,
            currency=body.currency,
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return _event_out(event)
    except HTTPException:
        raise
    except Exception as e:
        log.error("log_event failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{customer_id}/summary")
async def get_summary(
    customer_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        events = (
            await db.execute(
                select(CustomerHistoryEvent).where(
                    CustomerHistoryEvent.org_id == org_id,
                    CustomerHistoryEvent.customer_id == customer_id,
                )
            )
        ).scalars().all()

        total_appointments = sum(1 for e in events if e.event_type == "appointment")
        total_spend = sum(
            float(e.amount)
            for e in events
            if e.event_type in ("purchase", "invoice") and e.amount is not None
        )
        loyalty_points_earned = sum(
            float(e.amount)
            for e in events
            if e.event_type == "loyalty_earn" and e.amount is not None
        )
        appointment_dates = [
            e.event_date for e in events if e.event_type == "appointment"
        ]
        last_visit = max(appointment_dates).isoformat() if appointment_dates else None
        all_dates = [e.event_date for e in events]
        member_since = min(all_dates).isoformat() if all_dates else None

        return {
            "customer_id": str(customer_id),
            "total_appointments": total_appointments,
            "total_spend": round(total_spend, 2),
            "loyalty_points_earned": round(loyalty_points_earned, 2),
            "last_visit": last_visit,
            "member_since": member_since,
        }
    except Exception as e:
        log.error("get_summary failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{customer_id}/backfill")
async def backfill_history(
    customer_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Auto-populate history from existing Appointment, Invoice, and Payment data."""
    org_id = _org_id(ctx)
    try:
        created = 0
        skipped = 0

        # Helper: check if a history event already exists for a reference
        async def _exists(ref_id: uuid.UUID, ref_type: str) -> bool:
            row = await db.scalar(
                select(CustomerHistoryEvent).where(
                    CustomerHistoryEvent.org_id == org_id,
                    CustomerHistoryEvent.customer_id == customer_id,
                    CustomerHistoryEvent.reference_id == ref_id,
                    CustomerHistoryEvent.reference_type == ref_type,
                )
            )
            return row is not None

        # --- Appointments ---
        appointments = (
            await db.execute(
                select(Appointment).where(
                    Appointment.org_id == org_id,
                    Appointment.customer_id == customer_id,
                )
            )
        ).scalars().all()

        for appt in appointments:
            if await _exists(appt.id, "appointment"):
                skipped += 1
                continue
            db.add(
                CustomerHistoryEvent(
                    org_id=org_id,
                    customer_id=customer_id,
                    event_type="appointment",
                    event_date=appt.start_time,
                    title=f"Appointment — {appt.status}",
                    reference_id=appt.id,
                    reference_type="appointment",
                )
            )
            created += 1

        # --- Invoices ---
        invoices = (
            await db.execute(
                select(Invoice).where(
                    Invoice.org_id == org_id,
                    Invoice.customer_id == customer_id,
                )
            )
        ).scalars().all()

        for inv in invoices:
            if await _exists(inv.id, "invoice"):
                skipped += 1
                continue
            # issue_date is a date object; convert to datetime for event_date
            event_date = datetime(
                inv.issue_date.year,
                inv.issue_date.month,
                inv.issue_date.day,
                tzinfo=timezone.utc,
            )
            db.add(
                CustomerHistoryEvent(
                    org_id=org_id,
                    customer_id=customer_id,
                    event_type="invoice",
                    event_date=event_date,
                    title=f"Invoice — {inv.total_sek} {inv.currency}",
                    reference_id=inv.id,
                    reference_type="invoice",
                    amount=inv.total_sek,
                    currency=inv.currency,
                )
            )
            created += 1

        # --- Payments ---
        payments = (
            await db.execute(
                select(Payment).where(
                    Payment.org_id == org_id,
                )
                # Payment has no direct customer_id; join via Invoice
                .join(Invoice, Invoice.id == Payment.invoice_id)
                .where(Invoice.customer_id == customer_id)
            )
        ).scalars().all()

        for pay in payments:
            if await _exists(pay.id, "payment"):
                skipped += 1
                continue
            event_date = datetime(
                pay.payment_date.year,
                pay.payment_date.month,
                pay.payment_date.day,
                tzinfo=timezone.utc,
            )
            db.add(
                CustomerHistoryEvent(
                    org_id=org_id,
                    customer_id=customer_id,
                    event_type="purchase",
                    event_date=event_date,
                    title=f"Payment — {pay.amount} {pay.currency}",
                    reference_id=pay.id,
                    reference_type="payment",
                    amount=pay.amount,
                    currency=pay.currency,
                )
            )
            created += 1

        await db.commit()
        return {"created": created, "skipped": skipped}
    except HTTPException:
        raise
    except Exception as e:
        log.error("backfill_history failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
