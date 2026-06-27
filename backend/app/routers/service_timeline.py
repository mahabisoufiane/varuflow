"""Service Timelines — ordered stage tracking for appointments/orders.

Endpoints
─────────
GET    /api/timelines                              → list timelines for org
POST   /api/timelines                              → create timeline (+ optional bulk events)
GET    /api/timelines/appointment/{appointment_id} → timelines for appointment
GET    /api/timelines/{id}                         → detail with events
PATCH  /api/timelines/{id}                         → update title
DELETE /api/timelines/{id}                         → delete (cascades events)
POST   /api/timelines/{id}/events                  → add event
PATCH  /api/timelines/events/{event_id}            → update event
DELETE /api/timelines/events/{event_id}            → delete event
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.service_timeline import ServiceTimeline, ServiceTimelineEvent

router = APIRouter(prefix="/api/timelines", tags=["timelines"])
log = logging.getLogger(__name__)

_VALID_STATUSES = {"pending", "in_progress", "completed", "skipped"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _event_out(e: ServiceTimelineEvent) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "timeline_id": str(e.timeline_id),
        "stage": e.stage,
        "label": e.label,
        "description": e.description,
        "status": e.status,
        "completed_at": e.completed_at.isoformat() if e.completed_at else None,
        "sort_order": e.sort_order,
        "created_at": e.created_at.isoformat(),
    }


def _timeline_out(t: ServiceTimeline, include_events: bool = True) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": str(t.id),
        "org_id": str(t.org_id),
        "appointment_id": str(t.appointment_id) if t.appointment_id else None,
        "order_id": str(t.order_id) if t.order_id else None,
        "customer_id": str(t.customer_id) if t.customer_id else None,
        "title": t.title,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
    }
    if include_events:
        d["events"] = [_event_out(e) for e in (t.events or [])]
    return d


# ── Schemas ────────────────────────────────────────────────────────────────────

class InitialEventIn(BaseModel):
    stage: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    sort_order: int = 0


class TimelineIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    appointment_id: Optional[uuid.UUID] = None
    order_id: Optional[uuid.UUID] = None
    customer_id: Optional[uuid.UUID] = None
    initial_events: Optional[List[InitialEventIn]] = None


class TimelinePatch(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class EventIn(BaseModel):
    stage: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    sort_order: int = 0


class EventPatch(BaseModel):
    label: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = None
    completed_at: Optional[datetime] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_timelines(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        rows = (
            await db.execute(
                select(ServiceTimeline)
                .where(ServiceTimeline.org_id == org_id)
                .order_by(ServiceTimeline.created_at.desc())
            )
        ).scalars().all()
        # Load events for each
        result = []
        for t in rows:
            events = (
                await db.execute(
                    select(ServiceTimelineEvent)
                    .where(ServiceTimelineEvent.timeline_id == t.id)
                    .order_by(ServiceTimelineEvent.sort_order)
                )
            ).scalars().all()
            t.events = events
            result.append(_timeline_out(t))
        return result
    except Exception as e:
        log.error("list_timelines failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_timeline(
    body: TimelineIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        timeline = ServiceTimeline(
            org_id=org_id,
            title=body.title,
            appointment_id=body.appointment_id,
            order_id=body.order_id,
            customer_id=body.customer_id,
        )
        db.add(timeline)
        await db.flush()

        events: list[ServiceTimelineEvent] = []
        if body.initial_events:
            for ev in body.initial_events:
                event = ServiceTimelineEvent(
                    timeline_id=timeline.id,
                    stage=ev.stage,
                    label=ev.label,
                    description=ev.description,
                    sort_order=ev.sort_order,
                )
                db.add(event)
                events.append(event)

        await db.commit()
        await db.refresh(timeline)
        # Refresh events after commit
        if events:
            for ev in events:
                await db.refresh(ev)
        timeline.events = events
        return _timeline_out(timeline)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_timeline failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# Declare BEFORE /{timeline_id} to prevent path collision
@router.get("/appointment/{appointment_id}")
async def list_timelines_for_appointment(
    appointment_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        rows = (
            await db.execute(
                select(ServiceTimeline).where(
                    ServiceTimeline.org_id == org_id,
                    ServiceTimeline.appointment_id == appointment_id,
                )
            )
        ).scalars().all()
        result = []
        for t in rows:
            events = (
                await db.execute(
                    select(ServiceTimelineEvent)
                    .where(ServiceTimelineEvent.timeline_id == t.id)
                    .order_by(ServiceTimelineEvent.sort_order)
                )
            ).scalars().all()
            t.events = events
            result.append(_timeline_out(t))
        return result
    except Exception as e:
        log.error(
            "list_timelines_for_appointment failed: %s", e,
            extra={"org_id": str(org_id)},
        )
        raise HTTPException(status_code=500, detail="Internal server error")


# Declare BEFORE /{timeline_id} to prevent collision with /events/{event_id}
@router.patch("/events/{event_id}")
async def patch_event(
    event_id: uuid.UUID,
    body: EventPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        event = await db.scalar(
            select(ServiceTimelineEvent).where(ServiceTimelineEvent.id == event_id)
        )
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        # Verify org ownership via timeline
        timeline = await db.scalar(
            select(ServiceTimeline).where(
                ServiceTimeline.id == event.timeline_id,
                ServiceTimeline.org_id == org_id,
            )
        )
        if not timeline:
            raise HTTPException(status_code=403, detail="Not authorised")

        if body.label is not None:
            event.label = body.label
        if body.description is not None:
            event.description = body.description
        if body.status is not None:
            if body.status not in _VALID_STATUSES:
                raise HTTPException(
                    status_code=422,
                    detail=f"status must be one of {sorted(_VALID_STATUSES)}",
                )
            event.status = body.status
            now = datetime.now(timezone.utc)
            if body.status == "completed":
                event.completed_at = body.completed_at or now
            elif body.status == "in_progress":
                # Mark all prior events (lower sort_order) as completed
                prior_events = (
                    await db.execute(
                        select(ServiceTimelineEvent).where(
                            ServiceTimelineEvent.timeline_id == event.timeline_id,
                            ServiceTimelineEvent.sort_order < event.sort_order,
                        )
                    )
                ).scalars().all()
                for prior in prior_events:
                    if prior.status != "completed":
                        prior.status = "completed"
                        if not prior.completed_at:
                            prior.completed_at = now
        elif body.completed_at is not None:
            event.completed_at = body.completed_at

        await db.commit()
        await db.refresh(event)
        return _event_out(event)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_event failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/events/{event_id}", status_code=204)
async def delete_event(
    event_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        event = await db.scalar(
            select(ServiceTimelineEvent).where(ServiceTimelineEvent.id == event_id)
        )
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        timeline = await db.scalar(
            select(ServiceTimeline).where(
                ServiceTimeline.id == event.timeline_id,
                ServiceTimeline.org_id == org_id,
            )
        )
        if not timeline:
            raise HTTPException(status_code=403, detail="Not authorised")

        await db.delete(event)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_event failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{timeline_id}")
async def get_timeline(
    timeline_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        timeline = await db.scalar(
            select(ServiceTimeline).where(
                ServiceTimeline.id == timeline_id,
                ServiceTimeline.org_id == org_id,
            )
        )
        if not timeline:
            raise HTTPException(status_code=404, detail="Timeline not found")

        events = (
            await db.execute(
                select(ServiceTimelineEvent)
                .where(ServiceTimelineEvent.timeline_id == timeline.id)
                .order_by(ServiceTimelineEvent.sort_order)
            )
        ).scalars().all()
        timeline.events = events
        return _timeline_out(timeline)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_timeline failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{timeline_id}")
async def patch_timeline(
    timeline_id: uuid.UUID,
    body: TimelinePatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        timeline = await db.scalar(
            select(ServiceTimeline).where(
                ServiceTimeline.id == timeline_id,
                ServiceTimeline.org_id == org_id,
            )
        )
        if not timeline:
            raise HTTPException(status_code=404, detail="Timeline not found")

        timeline.title = body.title
        timeline.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(timeline)

        events = (
            await db.execute(
                select(ServiceTimelineEvent)
                .where(ServiceTimelineEvent.timeline_id == timeline.id)
                .order_by(ServiceTimelineEvent.sort_order)
            )
        ).scalars().all()
        timeline.events = events
        return _timeline_out(timeline)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_timeline failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{timeline_id}", status_code=204)
async def delete_timeline(
    timeline_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        timeline = await db.scalar(
            select(ServiceTimeline).where(
                ServiceTimeline.id == timeline_id,
                ServiceTimeline.org_id == org_id,
            )
        )
        if not timeline:
            raise HTTPException(status_code=404, detail="Timeline not found")
        await db.delete(timeline)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_timeline failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{timeline_id}/events", status_code=201)
async def add_event(
    timeline_id: uuid.UUID,
    body: EventIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        timeline = await db.scalar(
            select(ServiceTimeline).where(
                ServiceTimeline.id == timeline_id,
                ServiceTimeline.org_id == org_id,
            )
        )
        if not timeline:
            raise HTTPException(status_code=404, detail="Timeline not found")

        event = ServiceTimelineEvent(
            timeline_id=timeline_id,
            stage=body.stage,
            label=body.label,
            description=body.description,
            sort_order=body.sort_order,
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return _event_out(event)
    except HTTPException:
        raise
    except Exception as e:
        log.error("add_event failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
