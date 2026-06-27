"""Regulatory Calendar — track compliance events and filing deadlines.

Endpoints
─────────
GET    /api/regulatory/upcoming          → events due soon or overdue
GET    /api/regulatory                   → list events (filter: country, status)
POST   /api/regulatory                   → create event
GET    /api/regulatory/{id}              → detail
PATCH  /api/regulatory/{id}              → update / mark completed
DELETE /api/regulatory/{id}              → delete
POST   /api/regulatory/seed/{country}    → seed standard events for SE / NO / DK
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
from .regulatory_calendar_models import RegulatoryEvent
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/regulatory", tags=["regulatory_calendar"], dependencies=[Depends(require_module("analytics"))])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _event_out(e: RegulatoryEvent) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "org_id": str(e.org_id),
        "title": e.title,
        "event_type": e.event_type,
        "country": e.country,
        "due_date": e.due_date.isoformat() if e.due_date else None,
        "recurrence": e.recurrence,
        "status": e.status,
        "notes": e.notes,
        "alert_days": e.alert_days,
        "created_at": e.created_at.isoformat(),
        "updated_at": e.updated_at.isoformat(),
    }


def _seed_templates(country: str, year: int) -> list[dict]:
    """Return seed event dicts for country (SE/NO/DK)."""
    ny = year + 1  # next year for events that fall in Jan/Feb of following year
    if country == "SE":
        return [
            {"title": "Momsredovisning Q1", "event_type": "vat_filing",    "due_date": date(year, 5, 12),  "recurrence": "quarterly"},
            {"title": "Momsredovisning Q2", "event_type": "vat_filing",    "due_date": date(year, 8, 12),  "recurrence": "quarterly"},
            {"title": "Momsredovisning Q3", "event_type": "vat_filing",    "due_date": date(year, 11, 12), "recurrence": "quarterly"},
            {"title": "Momsredovisning Q4", "event_type": "vat_filing",    "due_date": date(ny,   2, 12),  "recurrence": "quarterly"},
            {"title": "Inkomstdeklaration", "event_type": "annual_report", "due_date": date(year, 7, 1),   "recurrence": "annually"},
            {"title": "Arbetsgivardeklaration (annual)", "event_type": "payroll_submission", "due_date": date(year, 1, 31), "recurrence": "annually"},
        ]
    if country == "NO":
        return [
            {"title": "MVA-melding termin 1", "event_type": "vat_filing",    "due_date": date(year, 4, 10),  "recurrence": "quarterly"},
            {"title": "MVA-melding termin 2", "event_type": "vat_filing",    "due_date": date(year, 6, 10),  "recurrence": "quarterly"},
            {"title": "MVA-melding termin 3", "event_type": "vat_filing",    "due_date": date(year, 8, 31),  "recurrence": "quarterly"},
            {"title": "MVA-melding termin 4", "event_type": "vat_filing",    "due_date": date(year, 10, 10), "recurrence": "quarterly"},
            {"title": "MVA-melding termin 5", "event_type": "vat_filing",    "due_date": date(year, 12, 10), "recurrence": "quarterly"},
            {"title": "MVA-melding termin 6", "event_type": "vat_filing",    "due_date": date(ny,   2, 10),  "recurrence": "quarterly"},
            {"title": "Skattemelding",        "event_type": "annual_report", "due_date": date(year, 4, 30),  "recurrence": "annually"},
        ]
    if country == "DK":
        return [
            {"title": "Momsangivelse Q1", "event_type": "vat_filing",    "due_date": date(year, 5, 1),  "recurrence": "quarterly"},
            {"title": "Momsangivelse Q2", "event_type": "vat_filing",    "due_date": date(year, 8, 1),  "recurrence": "quarterly"},
            {"title": "Momsangivelse Q3", "event_type": "vat_filing",    "due_date": date(year, 11, 1), "recurrence": "quarterly"},
            {"title": "Momsangivelse Q4", "event_type": "vat_filing",    "due_date": date(ny,   2, 1),  "recurrence": "quarterly"},
            {"title": "Selskabsskat",     "event_type": "annual_report", "due_date": date(year, 6, 30), "recurrence": "annually"},
        ]
    return []


# ── Schemas ────────────────────────────────────────────────────────────────────

class EventIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    event_type: str = Field(default="other")
    country: str = Field(max_length=3)
    due_date: date
    recurrence: str = Field(default="once")
    status: str = Field(default="upcoming")
    notes: Optional[str] = None
    alert_days: int = Field(default=14)


class EventPatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=300)
    event_type: Optional[str] = None
    country: Optional[str] = Field(default=None, max_length=3)
    due_date: Optional[date] = None
    recurrence: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    alert_days: Optional[int] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/upcoming")
async def upcoming_events(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Events where due_date <= today + alert_days OR overdue, sorted by due_date."""
    org_id = _org_id(ctx)
    try:
        today = date.today()
        rows = (await db.execute(
            select(RegulatoryEvent).where(RegulatoryEvent.org_id == org_id)
            .order_by(RegulatoryEvent.due_date.asc())
        )).scalars().all()

        result = []
        for e in rows:
            if e.due_date is None:
                continue
            cutoff = today + timedelta(days=e.alert_days or 14)
            if e.due_date <= cutoff or e.status == "overdue":
                result.append(_event_out(e))
        return result
    except Exception as e:
        log.error("upcoming_events failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("")
async def list_events(
    country: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = select(RegulatoryEvent).where(RegulatoryEvent.org_id == org_id)
        if country:
            q = q.where(RegulatoryEvent.country == country)
        if status:
            q = q.where(RegulatoryEvent.status == status)
        q = q.order_by(RegulatoryEvent.due_date.asc())
        rows = (await db.execute(q)).scalars().all()
        return [_event_out(e) for e in rows]
    except Exception as e:
        log.error("list_events failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_event(
    body: EventIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        event = RegulatoryEvent(
            org_id=org_id,
            title=body.title,
            event_type=body.event_type,
            country=body.country,
            due_date=body.due_date,
            recurrence=body.recurrence,
            status=body.status,
            notes=body.notes,
            alert_days=body.alert_days,
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return _event_out(event)
    except Exception as e:
        log.error("create_event failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{event_id}")
async def get_event(
    event_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        event = await db.scalar(
            select(RegulatoryEvent).where(
                RegulatoryEvent.id == event_id, RegulatoryEvent.org_id == org_id
            )
        )
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        return _event_out(event)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_event failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{event_id}")
async def patch_event(
    event_id: uuid.UUID,
    body: EventPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        event = await db.scalar(
            select(RegulatoryEvent).where(
                RegulatoryEvent.id == event_id, RegulatoryEvent.org_id == org_id
            )
        )
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        for field in ("title", "event_type", "country", "due_date", "recurrence", "status", "notes", "alert_days"):
            val = getattr(body, field)
            if val is not None:
                setattr(event, field, val)

        event.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(event)
        return _event_out(event)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_event failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{event_id}", status_code=204)
async def delete_event(
    event_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        event = await db.scalar(
            select(RegulatoryEvent).where(
                RegulatoryEvent.id == event_id, RegulatoryEvent.org_id == org_id
            )
        )
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        await db.delete(event)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_event failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/seed/{country}", status_code=201)
async def seed_country(
    country: str,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Seed standard regulatory events for SE, NO, or DK."""
    org_id = _org_id(ctx)
    country = country.upper()
    try:
        if country not in {"SE", "NO", "DK"}:
            raise HTTPException(status_code=422, detail="Supported countries: SE, NO, DK")

        year = datetime.now().year
        templates = _seed_templates(country, year)

        created = []
        for t in templates:
            # Check for duplicate by (org_id, title, due_date)
            existing = await db.scalar(
                select(RegulatoryEvent).where(
                    RegulatoryEvent.org_id == org_id,
                    RegulatoryEvent.title == t["title"],
                    RegulatoryEvent.due_date == t["due_date"],
                )
            )
            if existing:
                continue

            event = RegulatoryEvent(
                org_id=org_id,
                title=t["title"],
                event_type=t["event_type"],
                country=country,
                due_date=t["due_date"],
                recurrence=t["recurrence"],
                status="upcoming",
            )
            db.add(event)
            await db.flush()
            await db.refresh(event)
            created.append(_event_out(event))

        await db.commit()
        return created
    except HTTPException:
        raise
    except Exception as e:
        log.error("seed_country failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
