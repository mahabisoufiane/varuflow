"""Meeting link router: admin CRUD + public slot/booking endpoints.

The admin endpoints (list, create, update, delete) require get_current_member.
The slug-based endpoints (GET /{slug}, GET /{slug}/slots, POST /{slug}/book)
are intentionally PUBLIC — they are embedded on the salon's own website so
customers can book without a Varuflow account. Do NOT add auth to these.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from .meeting_links_models import MeetingLink

log = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_module("invoicing"))])

_VALID_SLUG = re.compile(r"^[a-z0-9-]{2,80}$")


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class MeetingLinkCreate(BaseModel):
    title: str
    slug: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: int = 30
    location: Optional[str] = None
    staff_id: Optional[uuid.UUID] = None
    buffer_minutes: int = 0
    min_notice_hours: int = 1
    is_active: bool = True


class MeetingLinkUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    location: Optional[str] = None
    staff_id: Optional[uuid.UUID] = None
    buffer_minutes: Optional[int] = None
    min_notice_hours: Optional[int] = None
    is_active: Optional[bool] = None


class BookingBody(BaseModel):
    name: str
    email: str
    notes: Optional[str] = None
    start_time: str  # ISO datetime string


# ── Serializer ───────────────────────────────────────────────────────────────

def _link_out(m: MeetingLink) -> dict:
    return {
        "id": str(m.id),
        "slug": m.slug,
        "title": m.title,
        "description": m.description,
        "duration_minutes": m.duration_minutes,
        "location": m.location,
        "staff_id": str(m.staff_id) if m.staff_id else None,
        "buffer_minutes": m.buffer_minutes,
        "min_notice_hours": m.min_notice_hours,
        "is_active": m.is_active,
        "created_at": m.created_at.isoformat(),
        "updated_at": m.updated_at.isoformat(),
    }


# ── Admin endpoints ──────────────────────────────────────────────────────────

@router.get("/api/crm/meeting-links")
async def list_meeting_links(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1].org_id
        result = await db.execute(
            select(MeetingLink)
            .where(MeetingLink.org_id == org_id)
            .order_by(MeetingLink.created_at.desc())
        )
        return [_link_out(m) for m in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_meeting_links failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/crm/meeting-links", status_code=201)
async def create_meeting_link(
    body: MeetingLinkCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1].org_id
        slug = body.slug or re.sub(r"[^a-z0-9-]", "-", body.title.lower())[:60]
        if not _VALID_SLUG.match(slug):
            raise HTTPException(status_code=422, detail="Invalid slug")
        existing = await db.execute(select(MeetingLink).where(MeetingLink.slug == slug))
        if existing.scalars().first():
            slug = f"{slug}-{str(uuid.uuid4())[:8]}"
        link = MeetingLink(
            id=uuid.uuid4(),
            org_id=org_id,
            staff_id=body.staff_id,
            slug=slug,
            title=body.title,
            description=body.description,
            duration_minutes=body.duration_minutes,
            location=body.location,
            buffer_minutes=body.buffer_minutes,
            min_notice_hours=body.min_notice_hours,
            is_active=body.is_active,
        )
        db.add(link)
        await db.commit()
        await db.refresh(link)
        return _link_out(link)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_meeting_link failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/crm/meeting-links/{link_id}")
async def update_meeting_link(
    link_id: uuid.UUID,
    body: MeetingLinkUpdate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1].org_id
        result = await db.execute(
            select(MeetingLink).where(and_(MeetingLink.id == link_id, MeetingLink.org_id == org_id))
        )
        link = result.scalars().first()
        if not link:
            raise HTTPException(status_code=404, detail="Meeting link not found")
        for field, val in body.model_dump(exclude_none=True).items():
            setattr(link, field, val)
        await db.commit()
        await db.refresh(link)
        return _link_out(link)
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_meeting_link failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/crm/meeting-links/{link_id}", status_code=204)
async def delete_meeting_link(
    link_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1].org_id
        result = await db.execute(
            select(MeetingLink).where(and_(MeetingLink.id == link_id, MeetingLink.org_id == org_id))
        )
        link = result.scalars().first()
        if not link:
            raise HTTPException(status_code=404, detail="Meeting link not found")
        await db.delete(link)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_meeting_link failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Public endpoints (no auth) ───────────────────────────────────────────────

@router.get("/api/meet/{slug}")
async def get_meeting_link_public(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(MeetingLink).where(and_(MeetingLink.slug == slug, MeetingLink.is_active.is_(True)))
        )
        link = result.scalars().first()
        if not link:
            raise HTTPException(status_code=404, detail="Meeting link not found")
        return {
            "title": link.title,
            "description": link.description,
            "duration_minutes": link.duration_minutes,
            "location": link.location,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_meeting_link_public failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/meet/{slug}/slots")
async def get_slots(
    slug: str,
    day: str,
    db: AsyncSession = Depends(get_db),
):
    """Return available booking slots for a given day (YYYY-MM-DD)."""
    try:
        result = await db.execute(
            select(MeetingLink).where(and_(MeetingLink.slug == slug, MeetingLink.is_active.is_(True)))
        )
        link = result.scalars().first()
        if not link:
            raise HTTPException(status_code=404, detail="Meeting link not found")

        day_dt = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)

        # Load staff for working hours / existing appointments
        from .models import Staff, Appointment
        from app.services.booking_engine import compute_available_slots, TimeWindow
        from datetime import timedelta

        staff = None
        if link.staff_id:
            staff_result = await db.execute(select(Staff).where(Staff.id == link.staff_id))
            staff = staff_result.scalars().first()

        working_hours = staff.working_hours if staff else None
        break_times = staff.break_times if staff else None
        prayer_times = getattr(staff, "prayer_times", None) if staff else None

        # Existing appointments for this staff+day
        day_end = day_dt + timedelta(days=1)
        existing: list[TimeWindow] = []
        if staff:
            appt_result = await db.execute(
                select(Appointment).where(
                    and_(
                        Appointment.staff_id == staff.id,
                        Appointment.start_time >= day_dt,
                        Appointment.start_time < day_end,
                        Appointment.status != "cancelled",
                    )
                )
            )
            for appt in appt_result.scalars().all():
                appt_end = appt.end_time
                if link.buffer_minutes:
                    appt_end = appt_end + timedelta(minutes=link.buffer_minutes)
                existing.append(TimeWindow(start=appt.start_time, end=appt_end))

        # Apply min_notice_hours
        min_notice = datetime.now(timezone.utc) + timedelta(hours=link.min_notice_hours)

        slots = compute_available_slots(
            day=day_dt,
            duration_minutes=link.duration_minutes,
            working_hours=working_hours,
            break_times=break_times,
            prayer_times=prayer_times,
            existing_appointments=existing,
            prayer_blocking_enabled=False,
        )
        # Filter out slots before min notice
        slots = [s for s in slots if s >= min_notice]
        return {"slots": [s.isoformat() for s in slots]}
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_slots failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/meet/{slug}/book", status_code=201)
async def book_meeting(
    slug: str,
    body: BookingBody,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(MeetingLink).where(and_(MeetingLink.slug == slug, MeetingLink.is_active.is_(True)))
        )
        link = result.scalars().first()
        if not link:
            raise HTTPException(status_code=404, detail="Meeting link not found")

        from datetime import timedelta

        start_time = datetime.fromisoformat(body.start_time.replace("Z", "+00:00"))
        end_time = start_time + timedelta(minutes=link.duration_minutes)

        # Send confirmation email to attendee
        try:
            from app.services.email import send_campaign_email
            await send_campaign_email(
                to_email=body.email,
                subject=f"Meeting confirmed: {link.title}",
                body_html=(
                    f"<p>Hi {body.name},</p>"
                    f"<p>Your meeting <strong>{link.title}</strong> is confirmed for "
                    f"{start_time.strftime('%Y-%m-%d %H:%M')} UTC.</p>"
                    f"<p>Duration: {link.duration_minutes} minutes</p>"
                    + (f"<p>Location: {link.location}</p>" if link.location else "")
                    + (f"<p>Notes: {body.notes}</p>" if body.notes else "")
                ),
                org_name="",
            )
        except Exception:
            log.warning("book_meeting: confirmation email failed for slug=%s", slug)

        return {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_minutes": link.duration_minutes,
            "title": link.title,
            "location": link.location,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("book_meeting failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
