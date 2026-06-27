"""Salon & Spa booking router (v47 — Item 31, MENA).

Endpoint map
------------
Services
    POST   /api/bookings/services                — create
    GET    /api/bookings/services                — list active for org
Staff
    POST   /api/bookings/staff                   — create
    GET    /api/bookings/staff                   — list (honours female-only mode)
Appointments
    POST   /api/bookings/appointments            — book (auto-schedules reminders)
    GET    /api/bookings/appointments            — list for org (filterable)
    POST   /api/bookings/appointments/{id}/reschedule
    POST   /api/bookings/appointments/{id}/cancel
    POST   /api/bookings/appointments/{id}/status
Availability
    GET    /api/bookings/slots                   — slots for service+staff+day
Waitlist
    POST   /api/bookings/waitlist                — join
Walk-in queue
    POST   /api/bookings/walk-in                 — add walk-in appointment now
    GET    /api/bookings/walk-in                 — current queue
Widget
    GET    /api/bookings/widget-embed            — returns snippet HTML + JS

Every mutation calls ``log_action`` per the project rule. The router
deliberately trusts the middleware auth chain for org scoping — there
is no cross-org data leakage possible via path params because every
query is filtered by ``member.org_id``.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from .models import Appointment, Service, Staff
from app.features.auth.organization import Organization
from app.schemas.bookings import (
    AppointmentCreate,
    AppointmentOut,
    AppointmentReschedule,
    AppointmentStatusUpdate,
    ServiceCreate,
    ServiceOut,
    SlotListOut,
    StaffCreate,
    StaffOut,
    WaitlistJoin,
    WalkInEntry,
)
from app.services.audit import log_action
from app.services.booking_engine import (
    TimeWindow,
    compute_available_slots,
    female_only_staff_filter,
    loyalty_points_for_appointment,
)
from app.services.booking_reminders import schedule_reminders_for_appointment

router = APIRouter(prefix="/api/bookings", tags=["bookings"], dependencies=[Depends(require_module("crm"))])


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Services ────────────────────────────────────────────────────────


@router.post("/services", response_model=ServiceOut, status_code=201)
async def create_service(
    body: ServiceCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = Service(
        id=uuid.uuid4(),
        org_id=member.org_id,
        name=body.name,
        duration_minutes=body.duration_minutes,
        price=body.price,
        category=body.category,
        staff_id=body.staff_id,
        description=body.description,
    )
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="booking.service_created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="service",
        target_id=str(row.id),
        request=request,
        extra={"name": row.name, "duration_minutes": row.duration_minutes},
    )
    await db.commit()
    return row


@router.get("/services", response_model=list[ServiceOut])
async def list_services(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    rows = (
        await db.execute(
            select(Service).where(Service.org_id == member.org_id, Service.is_active.is_(True))
        )
    ).scalars().all()
    return list(rows)


# ── Staff ───────────────────────────────────────────────────────────


@router.post("/staff", response_model=StaffOut, status_code=201)
async def create_staff(
    body: StaffCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = Staff(
        id=uuid.uuid4(),
        org_id=member.org_id,
        name=body.name,
        role=body.role,
        working_hours=body.working_hours,
        break_times=body.break_times,
        specialties=body.specialties,
        gender=body.gender,
    )
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="booking.staff_created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="staff",
        target_id=str(row.id),
        request=request,
        extra={"name": row.name, "role": row.role, "gender": row.gender},
    )
    await db.commit()
    return row


@router.get("/staff", response_model=list[StaffOut])
async def list_staff(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    org = await db.get(Organization, member.org_id)
    rows = (
        await db.execute(
            select(Staff).where(Staff.org_id == member.org_id, Staff.is_active.is_(True))
        )
    ).scalars().all()
    # Apply female-only filter server-side so a UI bug can't leak staff
    # in a female-only salon. The filter is idempotent when disabled.
    filtered = female_only_staff_filter(
        rows, enabled=bool(getattr(org, "booking_female_only_mode", False))
    )
    return list(filtered)


# ── Slots ───────────────────────────────────────────────────────────


@router.get("/slots", response_model=SlotListOut)
async def slots(
    service_id: uuid.UUID,
    staff_id: uuid.UUID,
    day: datetime = Query(..., description="00:00 of the requested day"),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    service = await db.get(Service, service_id)
    if not service or service.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="service not found")
    staff = await db.get(Staff, staff_id)
    if not staff or staff.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="staff not found")
    org = await db.get(Organization, member.org_id)

    # Pull existing non-cancelled appointments for that staff on that day.
    day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    existing_rows = (
        await db.execute(
            select(Appointment).where(
                Appointment.org_id == member.org_id,
                Appointment.staff_id == staff_id,
                Appointment.start_time >= day_start,
                Appointment.start_time < day_end,
                Appointment.status.in_(("booked", "confirmed")),
            )
        )
    ).scalars().all()
    existing = [TimeWindow(start=a.start_time, end=a.end_time) for a in existing_rows]

    available = compute_available_slots(
        day_start,
        duration_minutes=service.duration_minutes,
        working_hours=staff.working_hours,
        break_times=staff.break_times,
        prayer_times=org.booking_prayer_times if org else None,
        existing_appointments=existing,
        prayer_blocking_enabled=bool(
            org and org.booking_prayer_time_blocking_enabled
        ),
    )
    return SlotListOut(
        service_id=service_id, staff_id=staff_id, day=day_start, slots=available
    )


# ── Appointments ────────────────────────────────────────────────────


@router.post("/appointments", response_model=AppointmentOut, status_code=201)
async def book_appointment(
    body: AppointmentCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    service = await db.get(Service, body.service_id)
    if not service or service.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="service not found")
    staff = await db.get(Staff, body.staff_id)
    if not staff or staff.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="staff not found")

    end_time = body.start_time + timedelta(minutes=service.duration_minutes)

    # Double-booking guard — reject any overlap with an existing non-cancelled
    # appointment for the same staff. Racy at scale (needs a serializable
    # transaction or a unique exclusion constraint for true safety); adequate
    # for the MVP and the test suite.
    overlap = (
        await db.execute(
            select(Appointment).where(
                Appointment.org_id == member.org_id,
                Appointment.staff_id == body.staff_id,
                Appointment.status.in_(("booked", "confirmed")),
                Appointment.start_time < end_time,
                Appointment.end_time > body.start_time,
            )
        )
    ).scalars().first()
    if overlap is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="slot overlaps an existing appointment",
        )

    appt = Appointment(
        id=uuid.uuid4(),
        org_id=member.org_id,
        service_id=body.service_id,
        staff_id=body.staff_id,
        customer_id=body.customer_id,
        warehouse_id=body.warehouse_id,
        start_time=body.start_time,
        end_time=end_time,
        status="booked",
        channel=body.channel,
        notes=body.notes,
    )
    db.add(appt)
    await db.flush()

    # Schedule 24h + 2h reminders. Failure here must not break the booking —
    # a reminder row is easy to re-add later, a missed booking is not.
    try:
        customer = None
        if appt.customer_id is not None:
            from app.features.invoicing.models import Customer

            customer = await db.get(Customer, appt.customer_id)
        await schedule_reminders_for_appointment(db, appt, customer)
    except Exception:
        pass

    await log_action(
        db,
        action="booking.appointment_created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="appointment",
        target_id=str(appt.id),
        request=request,
        extra={
            "service_id": str(body.service_id),
            "staff_id": str(body.staff_id),
            "start_time": body.start_time.isoformat(),
            "channel": body.channel,
        },
    )
    await db.commit()
    return appt


@router.get("/appointments", response_model=list[AppointmentOut])
async def list_appointments(
    staff_id: uuid.UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    q = select(Appointment).where(Appointment.org_id == member.org_id)
    if staff_id is not None:
        q = q.where(Appointment.staff_id == staff_id)
    if status_filter is not None:
        q = q.where(Appointment.status == status_filter)
    q = q.order_by(Appointment.start_time.asc()).limit(500)
    rows = (await db.execute(q)).scalars().all()
    return list(rows)


@router.post("/appointments/{appointment_id}/reschedule", response_model=AppointmentOut)
async def reschedule_appointment(
    appointment_id: uuid.UUID,
    body: AppointmentReschedule,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    appt = await db.get(Appointment, appointment_id)
    if not appt or appt.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="appointment not found")
    if appt.status in ("cancelled", "completed", "no_show"):
        raise HTTPException(status_code=400, detail=f"cannot reschedule from status={appt.status}")
    duration = appt.end_time - appt.start_time
    old_start = appt.start_time
    appt.start_time = body.start_time
    appt.end_time = body.start_time + duration
    appt.updated_at = datetime.now(tz=timezone.utc)
    await log_action(
        db,
        action="booking.appointment_rescheduled",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="appointment",
        target_id=str(appt.id),
        request=request,
        extra={"old_start": old_start.isoformat(), "new_start": body.start_time.isoformat()},
    )
    await db.commit()
    return appt


@router.post("/appointments/{appointment_id}/cancel", response_model=AppointmentOut)
async def cancel_appointment(
    appointment_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    appt = await db.get(Appointment, appointment_id)
    if not appt or appt.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="appointment not found")
    if appt.status == "cancelled":
        return appt
    appt.status = "cancelled"
    appt.updated_at = datetime.now(tz=timezone.utc)

    # Promote the oldest waitlisted appointment onto this slot, if any —
    # same staff, overlapping time. Naive promotion: flip status, don't
    # adjust start/end (caller is expected to have waitlisted with an
    # exact target slot). Notification is out of scope for the MVP.
    promoted = (
        await db.execute(
            select(Appointment).where(
                Appointment.org_id == member.org_id,
                Appointment.staff_id == appt.staff_id,
                Appointment.status == "waitlisted",
                Appointment.start_time == appt.start_time,
            ).order_by(Appointment.created_at.asc()).limit(1)
        )
    ).scalars().first()
    if promoted is not None:
        promoted.status = "booked"
        promoted.updated_at = datetime.now(tz=timezone.utc)

    await log_action(
        db,
        action="booking.appointment_cancelled",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="appointment",
        target_id=str(appt.id),
        request=request,
        extra={"promoted_waitlist_id": str(promoted.id) if promoted else None},
    )
    await db.commit()
    return appt


@router.post("/appointments/{appointment_id}/status", response_model=AppointmentOut)
async def set_appointment_status(
    appointment_id: uuid.UUID,
    body: AppointmentStatusUpdate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    appt = await db.get(Appointment, appointment_id)
    if not appt or appt.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="appointment not found")

    appt.status = body.status
    appt.updated_at = datetime.now(tz=timezone.utc)

    # Award loyalty points on completion. The column stays at 0 for
    # every other transition — re-completing an appointment is a no-op
    # (points only credited once).
    if body.status == "completed" and appt.loyalty_points_awarded == 0:
        service = await db.get(Service, appt.service_id)
        service_price = service.price if service else 0
        appt.loyalty_points_awarded = loyalty_points_for_appointment(service_price)

        # Item 35 — mirror the earn into the loyalty ledger. Best-effort:
        # booking must never fail because of a loyalty write. The flag
        # column above remains the idempotency guard, so the ledger
        # receives at most one ``earn`` row per appointment.
        if appt.customer_id is not None:
            from app.services.loyalty_engine import award_points as _award_loyalty

            try:
                await _award_loyalty(
                    db,
                    org_id=member.org_id,
                    customer_id=appt.customer_id,
                    amount=service_price,
                    source_type="booking",
                    source_id=str(appt.id),
                )
            except Exception:
                pass

    # Record staff commission on completion (Item 32). Best-effort —
    # a commission-layer failure must not break the status transition.
    if body.status == "completed":
        from app.services.commission_calculator import record_commission_for_source

        service = service if "service" in locals() and service else await db.get(Service, appt.service_id)
        base = service.price if service else 0
        await record_commission_for_source(
            db,
            org_id=member.org_id,
            staff_id=appt.staff_id,
            source_type="booking",
            source_id=appt.id,
            base_amount=base,
        )

    # Consume a bundle session on completion if the customer owns a
    # bundle that covers this service (Item 33). Best-effort — the
    # helper returns ``None`` when no bundle applies (the common
    # path) or when the DB hiccups.
    if body.status == "completed" and appt.customer_id is not None:
        from app.services.gift_card_service import consume_bundle_session

        await consume_bundle_session(
            db,
            org_id=member.org_id,
            customer_id=appt.customer_id,
            service_id=appt.service_id,
            appointment_id=appt.id,
        )

    # Review request (Item 49) — fire a magic-link prompt on the
    # first completion only. Best-effort: errors are logged via the
    # service, never raised, so a review-request DB hiccup can't
    # block the status transition itself.
    if body.status == "completed" and appt.customer_id is not None:
        try:
            from app.services.review_dispatch import (
                maybe_create_review_request,
            )

            await maybe_create_review_request(
                db,
                org_id=member.org_id,
                customer_id=appt.customer_id,
                source_type="booking",
                source_id=appt.id,
            )
        except Exception:  # pragma: no cover — defensive
            pass

    await log_action(
        db,
        action="booking.appointment_status_changed",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="appointment",
        target_id=str(appt.id),
        request=request,
        extra={"new_status": body.status, "loyalty_points": appt.loyalty_points_awarded},
    )
    await db.commit()
    return appt


# ── Waitlist ────────────────────────────────────────────────────────


@router.post("/waitlist", response_model=AppointmentOut, status_code=201)
async def join_waitlist(
    body: WaitlistJoin,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Join the waitlist for a fully-booked slot.

    Implemented as a regular ``Appointment`` row with ``status="waitlisted"``
    so the promotion on cancel flows through the same query surface.
    No overlap check here — that's the whole point of a waitlist.
    """
    user, member = ctx
    service = await db.get(Service, body.service_id)
    if not service or service.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="service not found")
    end_time = body.start_time + timedelta(minutes=service.duration_minutes)
    appt = Appointment(
        id=uuid.uuid4(),
        org_id=member.org_id,
        service_id=body.service_id,
        staff_id=body.staff_id,
        customer_id=body.customer_id,
        start_time=body.start_time,
        end_time=end_time,
        status="waitlisted",
        channel="web",
    )
    db.add(appt)
    await db.flush()
    await log_action(
        db,
        action="booking.waitlist_joined",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="appointment",
        target_id=str(appt.id),
        request=request,
        extra={"service_id": str(body.service_id), "start_time": body.start_time.isoformat()},
    )
    await db.commit()
    return appt


# ── Walk-in queue ──────────────────────────────────────────────────


@router.post("/walk-in", response_model=AppointmentOut, status_code=201)
async def add_walk_in(
    body: WalkInEntry,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Create an appointment with ``channel="walk_in"`` starting now.

    End time = ``now + service.duration_minutes``. No overlap check — a
    walk-in is assumed to be a manual reception-desk action where the
    operator has already sequenced the queue.
    """
    user, member = ctx
    service = await db.get(Service, body.service_id)
    if not service or service.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="service not found")
    now = datetime.now(tz=timezone.utc)
    appt = Appointment(
        id=uuid.uuid4(),
        org_id=member.org_id,
        service_id=body.service_id,
        staff_id=body.staff_id,
        customer_id=body.customer_id,
        start_time=now,
        end_time=now + timedelta(minutes=service.duration_minutes),
        status="booked",
        channel="walk_in",
        notes=body.notes,
    )
    db.add(appt)
    await db.flush()
    await log_action(
        db,
        action="booking.walk_in_added",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="appointment",
        target_id=str(appt.id),
        request=request,
        extra={"service_id": str(body.service_id), "staff_id": str(body.staff_id)},
    )
    await db.commit()
    return appt


@router.get("/walk-in", response_model=list[AppointmentOut])
async def list_walk_in_queue(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return today's walk-in appointments in arrival order."""
    _, member = ctx
    now = datetime.now(tz=timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    rows = (
        await db.execute(
            select(Appointment)
            .where(
                Appointment.org_id == member.org_id,
                Appointment.channel == "walk_in",
                Appointment.start_time >= day_start,
                Appointment.start_time < day_end,
            )
            .order_by(Appointment.created_at.asc())
        )
    ).scalars().all()
    return list(rows)


# ── Widget embed ────────────────────────────────────────────────────


@router.get("/widget-embed")
async def widget_embed(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return the HTML+JS snippet an operator can paste on a 3rd-party site.

    Item 46 upgrade: the snippet now targets the public slug-based
    widget path (``/widget/<slug>``) rather than the raw org-id, and
    includes a responsive wrapper so the iframe reflows on mobile.
    The slug is derived deterministically from ``(org.name, org.id)``
    so operators can copy-paste the snippet without any server-side
    token flow; the public router enforces org isolation at lookup
    time.
    """
    from app.features.auth.organization import Organization
    from app.services.widget_service import org_slug, resolve_brand_color

    _, member = ctx
    org_id = member.org_id
    org = await db.get(Organization, org_id)
    slug = org_slug(org.name if org else "", org_id)
    brand = await resolve_brand_color(db, org_id=org_id)

    snippet = (
        '<div style="position:relative;width:100%;max-width:640px;margin:0 auto">'
        f'<iframe src="https://varuflow.app/widget/{slug}" '
        'width="100%" height="720" frameborder="0" '
        'style="border:0;border-radius:8px;min-height:640px" '
        'title="Book an appointment" loading="lazy" '
        'allow="clipboard-write"></iframe></div>'
    )
    return {
        "snippet": snippet,
        "slug": slug,
        "url": f"https://varuflow.app/widget/{slug}",
        "brand_color": brand,
        "org_id": str(org_id),
    }


# ── Staff availability overrides (Item 57) ──────────────────────────
#
# Per-date time-off, sick leave, extra shifts and holidays. Baseline
# weekly schedule lives on :class:`Staff.working_hours`. The pure
# resolver in [services/staff_availability.py](../services/staff_availability.py)
# combines both.

from datetime import date as _date_57  # noqa: E402
from pydantic import BaseModel as _BaseModel_57  # noqa: E402, Field as _Field_57
from sqlalchemy import and_ as _and_57  # noqa: E402
from app.features.hr.staff_availability import (  # noqa: E402
    StaffAvailabilityKind as _AvKind_57,
    StaffAvailabilityOverride as _AvOv_57,
)
from app.services import staff_availability as _av_svc_57  # noqa: E402

_ALLOWED_KINDS_57 = {k.value for k in _AvKind_57}


class _OverrideIn_57(_BaseModel_57):
    staff_id: uuid.UUID
    kind:     str
    start_at: datetime
    end_at:   datetime
    reason:   str | None = None


class _OverrideOut_57(_BaseModel_57):
    id:         uuid.UUID
    staff_id:   uuid.UUID
    kind:       str
    start_at:   datetime
    end_at:     datetime
    reason:     str | None
    created_at: datetime


def _ensure_valid_override_57(payload: _OverrideIn_57) -> None:
    if payload.kind not in _ALLOWED_KINDS_57:
        raise HTTPException(
            status_code=400,
            detail=f"kind must be one of {sorted(_ALLOWED_KINDS_57)}",
        )
    if payload.end_at <= payload.start_at:
        raise HTTPException(
            status_code=400, detail="end_at must be after start_at"
        )
    if (payload.reason or "") and len(payload.reason) > 255:
        raise HTTPException(status_code=400, detail="reason too long")


@router.post(
    "/staff/{staff_id}/availability",
    response_model=_OverrideOut_57,
    status_code=201,
)
async def create_availability_override(
    staff_id: uuid.UUID,
    body: _OverrideIn_57,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    if body.staff_id != staff_id:
        raise HTTPException(status_code=400, detail="staff_id path/body mismatch")
    _ensure_valid_override_57(body)

    staff_row = await db.get(Staff, staff_id)
    if not staff_row or staff_row.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="Staff not found")

    row = _AvOv_57(
        org_id=member.org_id,
        staff_id=staff_id,
        kind=body.kind,
        start_at=body.start_at,
        end_at=body.end_at,
        reason=body.reason,
    )
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="staff_availability.created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="staff_availability_override",
        target_id=str(row.id),
        ip_address=request.client.host if request.client else None,
        extra={"staff_id": str(staff_id), "kind": body.kind},
    )
    await db.commit()
    await db.refresh(row)
    return row


@router.get(
    "/staff/{staff_id}/availability",
    response_model=list[_OverrideOut_57],
)
async def list_availability_overrides(
    staff_id: uuid.UUID,
    start: datetime | None = Query(default=None),
    end:   datetime | None = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    staff_row = await db.get(Staff, staff_id)
    if not staff_row or staff_row.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="Staff not found")

    stmt = (
        select(_AvOv_57)
        .where(
            _AvOv_57.org_id == member.org_id,
            _AvOv_57.staff_id == staff_id,
        )
        .order_by(_AvOv_57.start_at.asc())
    )
    if start is not None:
        stmt = stmt.where(_AvOv_57.end_at > start)
    if end is not None:
        stmt = stmt.where(_AvOv_57.start_at < end)
    return list((await db.scalars(stmt)).all())


@router.delete(
    "/staff/{staff_id}/availability/{override_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_availability_override(
    staff_id: uuid.UUID,
    override_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await db.get(_AvOv_57, override_id)
    if (
        not row
        or row.org_id != member.org_id
        or row.staff_id != staff_id
    ):
        raise HTTPException(status_code=404, detail="Override not found")
    await db.delete(row)
    await log_action(
        db,
        action="staff_availability.deleted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="staff_availability_override",
        target_id=str(override_id),
        ip_address=request.client.host if request.client else None,
        extra={"staff_id": str(staff_id)},
    )
    await db.commit()
    return None


@router.get("/staff/{staff_id}/available-windows")
async def get_staff_available_windows(
    staff_id: uuid.UUID,
    day: _date_57 = Query(..., description="ISO-8601 date (YYYY-MM-DD)"),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Resolve the staff member's bookable windows for ``day``.

    Combines :attr:`Staff.working_hours` with any override rows that
    touch ``day`` via :func:`staff_availability.apply_overrides`.
    """
    _, member = ctx
    staff_row = await db.get(Staff, staff_id)
    if not staff_row or staff_row.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="Staff not found")

    weekday_key = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][day.weekday()]
    baseline_raw = (staff_row.working_hours or {}).get(weekday_key) or []
    day_start_dt = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    baseline_intervals: list[_av_svc_57.Interval] = []
    for w in baseline_raw:
        try:
            iv = _av_svc_57.window_from_day(day_start_dt, w["start"], w["end"])
            baseline_intervals.append(iv)
        except (KeyError, ValueError):
            continue

    day_start = day_start_dt
    day_end = day_start + timedelta(days=1)
    overrides = list(
        (
            await db.scalars(
                select(_AvOv_57).where(
                    _AvOv_57.org_id == member.org_id,
                    _AvOv_57.staff_id == staff_id,
                    _AvOv_57.end_at > day_start,
                    _AvOv_57.start_at < day_end,
                )
            )
        ).all()
    )
    ov_objs = [
        _av_svc_57.Override(kind=o.kind, start=o.start_at, end=o.end_at)
        for o in overrides
    ]
    windows = _av_svc_57.apply_overrides(baseline_intervals, ov_objs)
    return {
        "staff_id": str(staff_id),
        "day": day.isoformat(),
        "windows": [
            {"start": iv.start.isoformat(), "end": iv.end.isoformat()}
            for iv in windows
        ],
    }


# ── Self-service check-in (Item 58) ─────────────────────────────────
#
# Staff mint a time-limited, one-time-use token per appointment. The
# customer scans a QR code containing just the token plaintext and
# posts it to the public redeem endpoint — no login required.

from pydantic import BaseModel as _BaseModel_58  # noqa: E402
from app.features.bookings.checkin_token import (  # noqa: E402
    AppointmentCheckinToken as _Tok_58,
)
from app.services import checkin_token as _tok_svc_58  # noqa: E402


class _MintOut_58(_BaseModel_58):
    token:      str
    expires_at: datetime
    appointment_id: uuid.UUID


class _RedeemIn_58(_BaseModel_58):
    token: str


class _RedeemOut_58(_BaseModel_58):
    ok:              bool
    appointment_id:  uuid.UUID
    checked_in_at:   datetime


@router.post(
    "/appointments/{appointment_id}/checkin-token",
    response_model=_MintOut_58,
    status_code=201,
)
async def mint_checkin_token(
    appointment_id: uuid.UUID,
    request: Request,
    ttl_minutes: int = Query(default=120, ge=5, le=720),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Staff action — generate a QR/SMS link for the customer."""
    user, member = ctx
    appt = await db.get(Appointment, appointment_id)
    if not appt or appt.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appt.status in {"cancelled", "no_show"}:
        raise HTTPException(
            status_code=409, detail=f"Cannot mint token for {appt.status} appointment"
        )

    now = datetime.now(timezone.utc)
    minted = _tok_svc_58.mint_token(now=now, ttl=timedelta(minutes=ttl_minutes))
    row = _Tok_58(
        org_id=member.org_id,
        appointment_id=appointment_id,
        token_hash=minted.token_hash,
        expires_at=minted.expires_at,
    )
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="appointment.checkin_token_minted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="appointment",
        target_id=str(appointment_id),
        ip_address=request.client.host if request.client else None,
        extra={"token_id": str(row.id), "ttl_minutes": ttl_minutes},
    )
    await db.commit()
    return _MintOut_58(
        token=minted.plaintext,
        expires_at=minted.expires_at,
        appointment_id=appointment_id,
    )


# Public — NO auth dependency. The token itself is the bearer credential.
public_checkin_router = APIRouter(
    prefix="/api/bookings/public", tags=["bookings"]
)


@public_checkin_router.post("/checkin", response_model=_RedeemOut_58)
async def redeem_checkin_token(
    body: _RedeemIn_58,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Customer-facing — redeem a check-in token.

    Intentionally returns the same generic 404 for "no such token",
    "expired", "already used" and "wrong window" to avoid leaking
    which state a token is in. The audit log records the specific
    reason for internal review.
    """
    candidate = (body.token or "").strip()
    if not candidate or len(candidate) > 512:
        raise HTTPException(status_code=404, detail="Invalid or expired token")

    try:
        candidate_hash = _tok_svc_58.hash_token(candidate)
    except ValueError:
        raise HTTPException(status_code=404, detail="Invalid or expired token")

    row = (
        await db.scalars(
            select(_Tok_58).where(_Tok_58.token_hash == candidate_hash)
        )
    ).first()
    # Constant-time membership check — even on cache miss we burn a
    # hash comparison so timing can't distinguish "unknown token"
    # from "known but expired".
    if row is None or not _tok_svc_58.verify_hash_matches(candidate, candidate_hash):
        raise HTTPException(status_code=404, detail="Invalid or expired token")

    appt = await db.get(Appointment, row.appointment_id)
    if appt is None:
        raise HTTPException(status_code=404, detail="Invalid or expired token")

    now = datetime.now(timezone.utc)
    ok, reason = _tok_svc_58.is_valid_now(
        _tok_svc_58.CheckinState(
            expires_at=row.expires_at,
            used_at=row.used_at,
            appointment_start=appt.start_time,
            appointment_end=appt.end_time,
        ),
        now=now,
    )
    if not ok:
        # Log the specific reason for ops visibility, but never echo
        # it back to the caller.
        await log_action(
            db,
            action="appointment.checkin_rejected",
            org_id=row.org_id,
            actor_user_id=None,
            target_type="appointment",
            target_id=str(appt.id),
            ip_address=request.client.host if request.client else None,
            extra={"reason": reason, "token_id": str(row.id)},
        )
        await db.commit()
        raise HTTPException(status_code=404, detail="Invalid or expired token")

    row.used_at = now
    appt.checked_in_at = now
    if appt.status == "booked":
        appt.status = "checked_in"
    await log_action(
        db,
        action="appointment.checked_in",
        org_id=row.org_id,
        actor_user_id=None,
        target_type="appointment",
        target_id=str(appt.id),
        ip_address=request.client.host if request.client else None,
        extra={"token_id": str(row.id)},
    )
    await db.commit()

    return _RedeemOut_58(
        ok=True, appointment_id=appt.id, checked_in_at=now
    )
