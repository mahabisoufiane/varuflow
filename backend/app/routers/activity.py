"""Activity feed router (Item 62).

Endpoints
---------

    GET  /api/activity                 list feed (cursor paginated)
    GET  /api/activity/{type}/{id}     entity timeline
    POST /api/activity/note            staff-authored note event

Listing supports filters: ``action_prefix`` (e.g. ``invoice.``),
``entity_type``, ``actor_user_id``, plus a ``cursor`` for keyset
pagination ordered by (``created_at`` DESC, ``id`` DESC).

Only the staff-note endpoint is a write path; the service module
exposes ``record_event`` helpers that other routers invoke internally
to produce events. That keeps business routers thin and callers
composable.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.activity_event import ActivityEvent
from app.services import activity as svc
from app.services.audit import log_action
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/activity", tags=["activity"], dependencies=[Depends(require_module("analytics"))])

log = logging.getLogger(__name__)


class NoteCreate(BaseModel):
    entity_type: str
    entity_id:   uuid.UUID
    summary:     str
    metadata:    dict | None = None


class EventOut(BaseModel):
    id:            uuid.UUID
    actor_user_id: uuid.UUID | None
    action:        str
    entity_type:   str | None
    entity_id:     uuid.UUID | None
    summary:       str
    metadata:      dict[str, Any]
    created_at:    datetime


class FeedPage(BaseModel):
    items:       list[EventOut]
    next_cursor: str | None


def _to_out(row: ActivityEvent) -> EventOut:
    return EventOut(
        id=row.id,
        actor_user_id=row.actor_user_id,
        action=row.action,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        summary=row.summary,
        metadata=dict(row.metadata_ or {}),
        created_at=row.created_at,
    )


async def _list_page(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    action_prefix: str | None = None,
    cursor: str | None = None,
    limit: int = svc.DEFAULT_LIMIT,
) -> FeedPage:
    stmt = select(ActivityEvent).where(ActivityEvent.org_id == org_id)

    if entity_type is not None:
        stmt = stmt.where(ActivityEvent.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(ActivityEvent.entity_id == entity_id)
    if actor_user_id is not None:
        stmt = stmt.where(ActivityEvent.actor_user_id == actor_user_id)
    if action_prefix:
        # Safe: we escape underscore/percent in the prefix so users
        # can't inject wildcards via the query param.
        safe = action_prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(ActivityEvent.action.like(f"{safe}%", escape="\\"))

    if cursor:
        try:
            ct, cid = svc.decode_cursor(cursor)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid cursor")
        stmt = stmt.where(
            or_(
                ActivityEvent.created_at < ct,
                and_(
                    ActivityEvent.created_at == ct,
                    ActivityEvent.id < cid,
                ),
            )
        )

    stmt = stmt.order_by(
        ActivityEvent.created_at.desc(), ActivityEvent.id.desc()
    ).limit(limit + 1)

    rows = list((await db.scalars(stmt)).all())
    next_cursor: str | None = None
    if len(rows) > limit:
        tail = rows[limit - 1]
        next_cursor = svc.encode_cursor(tail.created_at, tail.id)
        rows = rows[:limit]

    return FeedPage(items=[_to_out(r) for r in rows], next_cursor=next_cursor)


@router.get("", response_model=FeedPage)
async def list_activity(
    entity_type:    str | None = Query(default=None),
    actor_user_id:  uuid.UUID | None = Query(default=None),
    action_prefix:  str | None = Query(default=None),
    cursor:         str | None = Query(default=None),
    limit:          int | None = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _user, member = ctx
    try:
        entity_type = svc.validate_entity_type(entity_type)
        n = svc.clamp_limit(limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return await _list_page(
        db,
        org_id=member.org_id,
        entity_type=entity_type,
        actor_user_id=actor_user_id,
        action_prefix=action_prefix,
        cursor=cursor,
        limit=n,
    )


@router.get("/{entity_type}/{entity_id}", response_model=FeedPage)
async def list_entity_activity(
    entity_type: str,
    entity_id:   uuid.UUID,
    cursor:      str | None = Query(default=None),
    limit:       int | None = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _user, member = ctx
    try:
        etype = svc.validate_entity_type(entity_type)
        if etype is None:
            raise ValueError("entity_type required")
        n = svc.clamp_limit(limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return await _list_page(
        db,
        org_id=member.org_id,
        entity_type=etype,
        entity_id=entity_id,
        cursor=cursor,
        limit=n,
    )


@router.post("/note", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def add_note(
    body: NoteCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    try:
        etype = svc.validate_entity_type(body.entity_type)
        if etype is None:
            raise ValueError("entity_type required")
        summary = svc.validate_summary(body.summary)
        metadata = svc.validate_metadata(body.metadata)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    row = ActivityEvent(
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        action="note.added",
        entity_type=etype,
        entity_id=body.entity_id,
        summary=summary,
        metadata_=metadata,
    )
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="activity.note_added",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="activity_event",
        target_id=str(row.id),
        ip_address=request.client.host if request.client else None,
        extra={"entity_type": etype, "entity_id": str(body.entity_id)},
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)
