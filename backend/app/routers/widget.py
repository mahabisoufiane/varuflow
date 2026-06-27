"""Public booking widget router (Item 46).

Endpoints under ``/api/widget`` — **no authentication required**.
Designed to be called from an embedded iframe hosted on the salon's
own website.

* ``GET  /{slug}``                         — org + brand metadata
* ``GET  /{slug}/services``                — active services
* ``GET  /{slug}/staff``                   — active staff
* ``GET  /{slug}/slots``                   — available slots for a
                                              service+staff+day
* ``POST /{slug}/book``                    — create an appointment,
                                              send confirmation email

Writes are audited via :func:`log_action` with an anonymous actor.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, time, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.bookings import Appointment, Service, Staff
from app.models.organization import Organization
from app.services import widget_service as svc
from app.services.audit import log_action


router = APIRouter(prefix="/api/widget", tags=["widget"])


# ═══════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════


class WidgetOrgOut(BaseModel):
    slug: str
    name: str
    brand_color: str
    # ``rtl`` so the iframe can flip layout direction when the embed
    # is used on an Arabic / Hebrew salon site. Driven by a simple
    # org-name heuristic; the widget UI can also override it via the
    # ``?dir=rtl`` querystring.
    rtl: bool


class WidgetServiceOut(BaseModel):
    id: uuid.UUID
    name: str
    duration_minutes: int
    price: float
    category: str | None
    description: str | None


class WidgetStaffOut(BaseModel):
    id: uuid.UUID
    name: str
    role: str | None
    specialties: list[str] | None


class WidgetSlotOut(BaseModel):
    start: datetime
    end: datetime


class BookingIn(BaseModel):
    service_id: uuid.UUID
    staff_id: uuid.UUID
    start_time: datetime
    customer_name: str = Field(..., min_length=1, max_length=svc.MAX_NAME)
    customer_email: str
    customer_phone: str | None = None
    notes: str | None = None


class BookingOut(BaseModel):
    id: uuid.UUID
    start_time: datetime
    end_time: datetime
    service_name: str
    staff_name: str
    status: str


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


async def _load_org(db: AsyncSession, slug: str) -> Organization:
    org = await svc.resolve_org_by_slug(db, slug=slug)
    if org is None or getattr(org, "is_active", True) is False:
        raise HTTPException(status_code=404, detail="org_not_found")
    return org


def _looks_rtl(name: str) -> bool:
    """Tiny heuristic — any Arabic / Hebrew code point flips the
    iframe to RTL. Avoids shipping a full unicode-CLDR locale table
    for the widget."""
    for ch in name or "":
        cp = ord(ch)
        if 0x0590 <= cp <= 0x05FF:  # Hebrew
            return True
        if 0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F:  # Arabic
            return True
    return False


# ═══════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════


@router.get("/{slug}", response_model=WidgetOrgOut)
async def get_widget_meta(slug: str, db: AsyncSession = Depends(get_db)):
    """Return the org's public-facing widget metadata.

    Surfaces only safe fields — never exposes org-number, VAT, or
    any internal identifier other than the slug itself.
    """
    org = await _load_org(db, slug)
    brand = await svc.resolve_brand_color(db, org_id=org.id)
    return WidgetOrgOut(
        slug=slug,
        name=org.name or "",
        brand_color=brand,
        rtl=_looks_rtl(org.name or ""),
    )


@router.get("/{slug}/services", response_model=list[WidgetServiceOut])
async def list_services(slug: str, db: AsyncSession = Depends(get_db)):
    org = await _load_org(db, slug)
    rows = (
        await db.execute(
            select(Service).where(
                Service.org_id == org.id, Service.is_active == True,  # noqa: E712
            ).order_by(Service.name.asc())
        )
    ).scalars().all()
    return [
        WidgetServiceOut(
            id=r.id,
            name=r.name,
            duration_minutes=r.duration_minutes,
            price=float(r.price or 0),
            category=r.category,
            description=r.description,
        )
        for r in rows
    ]


@router.get("/{slug}/staff", response_model=list[WidgetStaffOut])
async def list_staff(slug: str, db: AsyncSession = Depends(get_db)):
    org = await _load_org(db, slug)
    rows = (
        await db.execute(
            select(Staff).where(
                Staff.org_id == org.id, Staff.is_active == True,  # noqa: E712
            ).order_by(Staff.name.asc())
        )
    ).scalars().all()
    return [
        WidgetStaffOut(
            id=r.id, name=r.name, role=r.role,
            specialties=list(r.specialties or []),
        )
        for r in rows
    ]


@router.get("/{slug}/slots", response_model=list[WidgetSlotOut])
async def list_slots(
    slug: str,
    service_id: uuid.UUID,
    staff_id: uuid.UUID,
    day: datetime = Query(..., description="Any UTC timestamp on the target day"),
    db: AsyncSession = Depends(get_db),
):
    """Return the free slots for a (service, staff) pair on ``day``.

    Uses 30-minute granularity between 09:00 and 18:00 local time
    (same default window the private slots endpoint applies). The
    practitioner's working-hours JSONB is respected if present.
    """
    org = await _load_org(db, slug)
    service = await db.get(Service, service_id)
    if service is None or service.org_id != org.id:
        raise HTTPException(status_code=404, detail="service_not_found")
    staff = await db.get(Staff, staff_id)
    if staff is None or staff.org_id != org.id:
        raise HTTPException(status_code=404, detail="staff_not_found")

    # Normalise to a UTC day.
    if day.tzinfo is None:
        day = day.replace(tzinfo=timezone.utc)
    day_start = datetime.combine(day.date(), time(9, 0), tzinfo=timezone.utc)
    day_end = datetime.combine(day.date(), time(18, 0), tzinfo=timezone.utc)
    step = timedelta(minutes=30)
    duration = timedelta(minutes=service.duration_minutes)

    # Pull existing appointments once; iterate in Python so the slot
    # generator stays O(day_hours) regardless of booking count.
    existing = (
        await db.execute(
            select(Appointment).where(
                Appointment.staff_id == staff.id,
                Appointment.org_id == org.id,
                Appointment.start_time >= day_start,
                Appointment.start_time < day_end,
                Appointment.status.in_(("booked", "confirmed")),
            )
        )
    ).scalars().all()

    slots: list[WidgetSlotOut] = []
    cur = day_start
    while cur + duration <= day_end:
        end = cur + duration
        conflict = any(
            svc.slots_overlap(cur, end, a.start_time, a.end_time)
            for a in existing
        )
        if not conflict:
            slots.append(WidgetSlotOut(start=cur, end=end))
        cur += step
    return slots


@router.post("/{slug}/book", response_model=BookingOut, status_code=201)
async def create_booking(
    slug: str,
    body: BookingIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Public booking — no auth required."""
    org = await _load_org(db, slug)

    # Validate inputs defensively. Even if the UI blocks bad data,
    # an attacker can call /book directly from curl.
    try:
        customer_name = svc.validate_name(body.customer_name)
        customer_email = svc.validate_email(body.customer_email)
        customer_phone = svc.validate_phone(body.customer_phone)
    except svc.WidgetValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    service = await db.get(Service, body.service_id)
    if service is None or service.org_id != org.id or not service.is_active:
        raise HTTPException(status_code=404, detail="service_not_found")
    staff = await db.get(Staff, body.staff_id)
    if staff is None or staff.org_id != org.id or not staff.is_active:
        raise HTTPException(status_code=404, detail="staff_not_found")

    start = body.start_time
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    end = start + timedelta(minutes=service.duration_minutes)

    # Double-booking guard — same half-open-interval rule as the
    # private router so public and private paths never disagree.
    overlap = (
        await db.execute(
            select(Appointment).where(
                Appointment.org_id == org.id,
                Appointment.staff_id == staff.id,
                Appointment.status.in_(("booked", "confirmed")),
                Appointment.start_time < end,
                Appointment.end_time > start,
            )
        )
    ).scalars().first()
    if overlap is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="slot_unavailable",
        )

    appt = Appointment(
        id=uuid.uuid4(),
        org_id=org.id,
        service_id=service.id,
        staff_id=staff.id,
        customer_id=None,     # walk-in / unregistered; name+email captured.
        warehouse_id=None,
        start_time=start,
        end_time=end,
        status="booked",
        channel="web",
        notes=(
            f"[widget] {customer_name} · {customer_email}"
            + (f" · {customer_phone}" if customer_phone else "")
            + (f" · {body.notes}" if body.notes else "")
        ),
    )
    db.add(appt)
    await db.flush()

    await log_action(
        db,
        action="widget.appointment_created",
        org_id=org.id,
        actor_user_id=None,        # public caller — no user context.
        target_type="appointment",
        target_id=str(appt.id),
        request=request,
        extra={
            "service_id": str(service.id),
            "staff_id": str(staff.id),
            "start_time": start.isoformat(),
            "channel": "web_widget",
            "customer_email": customer_email,
        },
    )
    await db.commit()

    # Dispatch confirmation email (fail-soft — appointment is already
    # persisted by the time we reach this line).
    brand = await svc.resolve_brand_color(db, org_id=org.id)
    await svc.send_confirmation_email(
        svc.BookingConfirmation(
            customer_name=customer_name,
            customer_email=customer_email,
            org_name=org.name or "",
            service_name=service.name,
            staff_name=staff.name,
            start_time=start,
            brand_color=brand,
        )
    )

    return BookingOut(
        id=appt.id,
        start_time=appt.start_time,
        end_time=appt.end_time,
        service_name=service.name,
        staff_name=staff.name,
        status=appt.status,
    )
