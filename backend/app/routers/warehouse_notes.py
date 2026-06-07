"""Warehouse notes router (Item 83).

Endpoints under ``/api/warehouse-notes``:

    GET    ""                    list notes (filter by warehouse_id)
    POST   ""                    create a note
    GET    /{note_id}             detail
    PATCH  /{note_id}             edit body (author only)
    DELETE /{note_id}             delete (author or OWNER/ADMIN)
    POST   /{note_id}/pin         pin   (any org member)
    POST   /{note_id}/unpin       unpin (any org member)

Authorship rule: editing a note is restricted to the original
author — backdating someone else's operations context would silently
rewrite audit history. Deletion is slightly more permissive —
OWNER/ADMIN can delete any note so bad content can be removed
without needing the original author available.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.inventory import Warehouse
from app.models.organization import OrgRole
from app.models.warehouse_note import WarehouseNote
from app.services import warehouse_note as svc_83
from app.services.audit import log_action
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/warehouse-notes", tags=["warehouse-notes"], dependencies=[Depends(require_module("inventory"))])

log = logging.getLogger(__name__)


class NoteCreate(BaseModel):
    warehouse_id: uuid.UUID
    body:         str
    is_pinned:    bool = False


class NoteUpdate(BaseModel):
    body: str


class NoteOut(BaseModel):
    id:             uuid.UUID
    warehouse_id:   uuid.UUID
    author_user_id: uuid.UUID
    body:           str
    is_pinned:      bool
    mentions:       list[str]
    created_at:     datetime
    updated_at:     datetime


# ── Helpers ───────────────────────────────────────────────────────────────


async def _assert_warehouse_belongs(
    db: AsyncSession, *, warehouse_id: uuid.UUID, org_id: uuid.UUID,
) -> None:
    found = await db.scalar(
        select(Warehouse.id).where(
            Warehouse.id == warehouse_id, Warehouse.org_id == org_id,
        )
    )
    if found is None:
        raise HTTPException(status_code=404, detail="Warehouse not found")


async def _load(
    db: AsyncSession, *, note_id: uuid.UUID, org_id: uuid.UUID,
) -> WarehouseNote:
    row = await db.get(WarehouseNote, note_id)
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Note not found")
    return row


def _to_out(row: WarehouseNote) -> NoteOut:
    return NoteOut(
        id=row.id,
        warehouse_id=row.warehouse_id,
        author_user_id=row.author_user_id,
        body=row.body,
        is_pinned=row.is_pinned,
        mentions=svc_83.extract_mentions(row.body),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _count_pinned(
    db: AsyncSession, *, warehouse_id: uuid.UUID, org_id: uuid.UUID,
    exclude_id: uuid.UUID | None = None,
) -> int:
    stmt = select(func.count(WarehouseNote.id)).where(
        WarehouseNote.org_id == org_id,
        WarehouseNote.warehouse_id == warehouse_id,
        WarehouseNote.is_pinned.is_(True),
    )
    if exclude_id is not None:
        stmt = stmt.where(WarehouseNote.id != exclude_id)
    return int((await db.execute(stmt)).scalar_one() or 0)


def _is_privileged(role: OrgRole) -> bool:
    return role in (OrgRole.OWNER, OrgRole.ADMIN)


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.get("", response_model=list[NoteOut])
async def list_notes(
    warehouse_id: uuid.UUID | None = Query(default=None),
    pinned_only:  bool = Query(default=False),
    limit:        int = Query(default=50, ge=1, le=200),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _user, member = ctx
    stmt = select(WarehouseNote).where(WarehouseNote.org_id == member.org_id)
    if warehouse_id is not None:
        stmt = stmt.where(WarehouseNote.warehouse_id == warehouse_id)
    if pinned_only:
        stmt = stmt.where(WarehouseNote.is_pinned.is_(True))
    # Pinned bubble up; ties break by newest-first.
    stmt = stmt.order_by(
        WarehouseNote.is_pinned.desc(),
        WarehouseNote.created_at.desc(),
    ).limit(limit)
    rows = (await db.scalars(stmt)).all()
    return [_to_out(r) for r in rows]


@router.post(
    "", response_model=NoteOut, status_code=status.HTTP_201_CREATED,
)
async def create_note(
    body:    NoteCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    await _assert_warehouse_belongs(
        db, warehouse_id=body.warehouse_id, org_id=member.org_id,
    )
    try:
        text = svc_83.validate_body(body.body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if body.is_pinned:
        existing = await _count_pinned(
            db, warehouse_id=body.warehouse_id, org_id=member.org_id,
        )
        try:
            svc_83.assert_pin_limit(current_pinned=existing)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    row = WarehouseNote(
        org_id=member.org_id,
        warehouse_id=body.warehouse_id,
        author_user_id=uuid.UUID(user["user_id"]),
        body=text,
        is_pinned=bool(body.is_pinned),
    )
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="warehouse_note.created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="warehouse_note",
        target_id=str(row.id),
        request=request,
        extra={
            "warehouse_id": str(body.warehouse_id),
            "pinned":       bool(body.is_pinned),
            "mentions":     svc_83.extract_mentions(text),
        },
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.get("/{note_id}", response_model=NoteOut)
async def get_note(
    note_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _user, member = ctx
    row = await _load(db, note_id=note_id, org_id=member.org_id)
    return _to_out(row)


@router.patch("/{note_id}", response_model=NoteOut)
async def update_note(
    note_id: uuid.UUID,
    body:    NoteUpdate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, note_id=note_id, org_id=member.org_id)
    if str(row.author_user_id) != str(user["user_id"]):
        raise HTTPException(
            status_code=403,
            detail="only the author may edit this note",
        )
    try:
        text = svc_83.validate_body(body.body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    row.body = text

    await db.flush()
    await log_action(
        db,
        action="warehouse_note.updated",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="warehouse_note",
        target_id=str(row.id),
        request=request,
        extra={"mentions": svc_83.extract_mentions(text)},
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, note_id=note_id, org_id=member.org_id)
    if (
        str(row.author_user_id) != str(user["user_id"])
        and not _is_privileged(member.role)
    ):
        raise HTTPException(
            status_code=403,
            detail="only the author or OWNER/ADMIN may delete this note",
        )
    await db.delete(row)
    await log_action(
        db,
        action="warehouse_note.deleted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="warehouse_note",
        target_id=str(note_id),
        request=request,
    )
    await db.commit()


@router.post("/{note_id}/pin", response_model=NoteOut)
async def pin_note(
    note_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, note_id=note_id, org_id=member.org_id)
    if row.is_pinned:
        # Idempotent — return the existing row rather than 409.
        return _to_out(row)

    existing = await _count_pinned(
        db,
        warehouse_id=row.warehouse_id,
        org_id=member.org_id,
        exclude_id=row.id,
    )
    try:
        svc_83.assert_pin_limit(current_pinned=existing)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    row.is_pinned = True
    await db.flush()
    await log_action(
        db,
        action="warehouse_note.pinned",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="warehouse_note",
        target_id=str(row.id),
        request=request,
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.post("/{note_id}/unpin", response_model=NoteOut)
async def unpin_note(
    note_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, note_id=note_id, org_id=member.org_id)
    if not row.is_pinned:
        return _to_out(row)
    row.is_pinned = False
    await db.flush()
    await log_action(
        db,
        action="warehouse_note.unpinned",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="warehouse_note",
        target_id=str(row.id),
        request=request,
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)
