"""Supplier notes router (Item 76).

Endpoints under ``/api/supplier-notes``:

    GET    ""                    list notes (filter by supplier_id)
    POST   ""                    create a note
    GET    /{note_id}             detail
    PATCH  /{note_id}             edit body (author only)
    DELETE /{note_id}             delete (author or OWNER/ADMIN)
    POST   /{note_id}/pin         pin   (any org member)
    POST   /{note_id}/unpin       unpin (any org member)

Authorship rule: editing a note is restricted to the original
author — backdating someone else's purchasing history would silently
rewrite audit context. Deletion is slightly more permissive —
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
from app.models.inventory import Supplier
from app.models.organization import OrgRole
from app.models.supplier_note import SupplierNote
from app.services import supplier_note as svc_76
from app.services.audit import log_action

router = APIRouter(prefix="/api/supplier-notes", tags=["supplier-notes"])

log = logging.getLogger(__name__)


class NoteCreate(BaseModel):
    supplier_id: uuid.UUID
    body:        str
    is_pinned:   bool = False


class NoteUpdate(BaseModel):
    body: str


class NoteOut(BaseModel):
    id:             uuid.UUID
    supplier_id:    uuid.UUID
    author_user_id: uuid.UUID
    body:           str
    is_pinned:      bool
    mentions:       list[str]
    created_at:     datetime
    updated_at:     datetime


# ── Helpers ───────────────────────────────────────────────────────────────


async def _assert_supplier_belongs(
    db: AsyncSession, *, supplier_id: uuid.UUID, org_id: uuid.UUID,
) -> None:
    found = await db.scalar(
        select(Supplier.id).where(
            Supplier.id == supplier_id, Supplier.org_id == org_id,
        )
    )
    if found is None:
        raise HTTPException(status_code=404, detail="Supplier not found")


async def _load(
    db: AsyncSession, *, note_id: uuid.UUID, org_id: uuid.UUID,
) -> SupplierNote:
    row = await db.get(SupplierNote, note_id)
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Note not found")
    return row


def _to_out(row: SupplierNote) -> NoteOut:
    return NoteOut(
        id=row.id,
        supplier_id=row.supplier_id,
        author_user_id=row.author_user_id,
        body=row.body,
        is_pinned=row.is_pinned,
        mentions=svc_76.extract_mentions(row.body),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _count_pinned(
    db: AsyncSession, *, supplier_id: uuid.UUID, org_id: uuid.UUID,
    exclude_id: uuid.UUID | None = None,
) -> int:
    stmt = select(func.count(SupplierNote.id)).where(
        SupplierNote.org_id == org_id,
        SupplierNote.supplier_id == supplier_id,
        SupplierNote.is_pinned.is_(True),
    )
    if exclude_id is not None:
        stmt = stmt.where(SupplierNote.id != exclude_id)
    return int((await db.execute(stmt)).scalar_one() or 0)


def _is_privileged(role: OrgRole) -> bool:
    return role in (OrgRole.OWNER, OrgRole.ADMIN)


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.get("", response_model=list[NoteOut])
async def list_notes(
    supplier_id: uuid.UUID | None = Query(default=None),
    pinned_only: bool = Query(default=False),
    limit:       int = Query(default=50, ge=1, le=200),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _user, member = ctx
    stmt = select(SupplierNote).where(SupplierNote.org_id == member.org_id)
    if supplier_id is not None:
        stmt = stmt.where(SupplierNote.supplier_id == supplier_id)
    if pinned_only:
        stmt = stmt.where(SupplierNote.is_pinned.is_(True))
    # Pinned bubble up; ties break by newest-first.
    stmt = stmt.order_by(
        SupplierNote.is_pinned.desc(),
        SupplierNote.created_at.desc(),
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
    await _assert_supplier_belongs(
        db, supplier_id=body.supplier_id, org_id=member.org_id,
    )
    try:
        text = svc_76.validate_body(body.body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if body.is_pinned:
        existing = await _count_pinned(
            db, supplier_id=body.supplier_id, org_id=member.org_id,
        )
        try:
            svc_76.assert_pin_limit(current_pinned=existing)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    row = SupplierNote(
        org_id=member.org_id,
        supplier_id=body.supplier_id,
        author_user_id=uuid.UUID(user["user_id"]),
        body=text,
        is_pinned=bool(body.is_pinned),
    )
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="supplier_note.created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="supplier_note",
        target_id=str(row.id),
        request=request,
        extra={
            "supplier_id": str(body.supplier_id),
            "pinned":      bool(body.is_pinned),
            "mentions":    svc_76.extract_mentions(text),
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
        text = svc_76.validate_body(body.body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    row.body = text

    await db.flush()
    await log_action(
        db,
        action="supplier_note.updated",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="supplier_note",
        target_id=str(row.id),
        request=request,
        extra={"mentions": svc_76.extract_mentions(text)},
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
        action="supplier_note.deleted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="supplier_note",
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
        supplier_id=row.supplier_id,
        org_id=member.org_id,
        exclude_id=row.id,
    )
    try:
        svc_76.assert_pin_limit(current_pinned=existing)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    row.is_pinned = True
    await db.flush()
    await log_action(
        db,
        action="supplier_note.pinned",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="supplier_note",
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
        action="supplier_note.unpinned",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="supplier_note",
        target_id=str(row.id),
        request=request,
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)
