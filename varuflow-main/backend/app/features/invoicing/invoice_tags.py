"""Invoice tags router (Item 87).

Endpoints under ``/api/invoice-tags``:

    GET    ""                          list tags in the org
    POST   ""                          create a tag
    GET    /{tag_id}                   detail (includes invoice_count)
    PATCH  /{tag_id}                   rename / recolor
    DELETE /{tag_id}                   delete (cascades to every
                                       assignment)
    GET    /{tag_id}/invoices          list invoices tagged with it
    POST   /assignments                attach a tag to an invoice
    DELETE /assignments                detach a tag from an invoice
    GET    /invoices/{invoice_id}      list tags on one invoice

Every mutation emits a single audit entry (``invoice_tag.created
/ updated / deleted / assigned / unassigned``) with
``request=request``.

Tags are a lightweight invoice-segmentation tool — names
normalise whitespace, case-insensitive uniqueness per org prevents
near-duplicates, and per-invoice assignment is capped at
:data:`~app.services.invoice_tag.MAX_TAGS_PER_INVOICE` (20) so
the tag chip list never overflows the invoice detail page.
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.features.invoicing.models import Invoice
from app.features.invoicing.invoice_tag import InvoiceTag, InvoiceTagAssignment
from app.services import invoice_tag as svc_87
from app.services.audit import log_action
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/invoice-tags", tags=["invoice-tags"], dependencies=[Depends(require_module("invoicing"))])

log = logging.getLogger(__name__)


# ── request bodies ──────────────────────────────────────────────────────


class TagCreate(BaseModel):
    name:  str
    color: str


class TagUpdate(BaseModel):
    name:  str | None = None
    color: str | None = None


class AssignmentIn(BaseModel):
    invoice_id: uuid.UUID
    tag_id:     uuid.UUID


# ── response bodies ─────────────────────────────────────────────────────


class TagOut(BaseModel):
    id:             uuid.UUID
    name:           str
    color:          str
    invoice_count:  int
    created_at:     datetime
    updated_at:     datetime


class InvoiceRef(BaseModel):
    id:             uuid.UUID
    invoice_number: str


# ── helpers ─────────────────────────────────────────────────────────────


async def _load_tag(
    db: AsyncSession, *, tag_id: uuid.UUID, org_id: uuid.UUID,
) -> InvoiceTag:
    row = await db.scalar(
        select(InvoiceTag).where(InvoiceTag.id == tag_id)
    )
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Tag not found")
    return row


async def _load_invoice(
    db: AsyncSession, *, invoice_id: uuid.UUID, org_id: uuid.UUID,
) -> Invoice:
    row = await db.scalar(
        select(Invoice).where(Invoice.id == invoice_id)
    )
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return row


async def _count_invoices(db: AsyncSession, *, tag_id: uuid.UUID) -> int:
    n = await db.scalar(
        select(func.count()).select_from(InvoiceTagAssignment)
        .where(InvoiceTagAssignment.tag_id == tag_id)
    )
    return int(n or 0)


async def _name_conflict(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    name: str,
    exclude_id: uuid.UUID | None = None,
) -> bool:
    stmt = select(InvoiceTag.id).where(
        InvoiceTag.org_id == org_id,
        func.lower(InvoiceTag.name) == name.lower(),
    )
    if exclude_id is not None:
        stmt = stmt.where(InvoiceTag.id != exclude_id)
    return (await db.scalar(stmt)) is not None


async def _to_out(db: AsyncSession, tag: InvoiceTag) -> TagOut:
    return TagOut(
        id=tag.id, name=tag.name, color=tag.color,
        invoice_count=await _count_invoices(db, tag_id=tag.id),
        created_at=tag.created_at, updated_at=tag.updated_at,
    )


# ── tag CRUD ────────────────────────────────────────────────────────────


@router.get("", response_model=list[TagOut])
async def list_tags(
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    rows = (await db.scalars(
        select(InvoiceTag)
        .where(InvoiceTag.org_id == member.org_id)
        .order_by(func.lower(InvoiceTag.name))
    )).all()
    return [await _to_out(db, r) for r in rows]


@router.post("", response_model=TagOut, status_code=status.HTTP_201_CREATED)
async def create_tag(
    payload: TagCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    try:
        name  = svc_87.normalize_name(payload.name)
        color = svc_87.normalize_color(payload.color)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if await _name_conflict(db, org_id=member.org_id, name=name):
        raise HTTPException(status_code=409, detail="Tag name already in use")

    tag = InvoiceTag(
        id=uuid.uuid4(),
        org_id=member.org_id,
        name=name,
        color=color,
        created_by_user_id=user["user_id"],
    )
    db.add(tag)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Tag name already in use")

    await log_action(
        db,
        action="invoice_tag.created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="invoice_tag",
        target_id=str(tag.id),
        request=request,
        extra={"name": tag.name, "color": tag.color},
    )
    await db.commit()
    await db.refresh(tag)
    return await _to_out(db, tag)


@router.get("/{tag_id}", response_model=TagOut)
async def get_tag(
    tag_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    tag = await _load_tag(db, tag_id=tag_id, org_id=member.org_id)
    return await _to_out(db, tag)


@router.patch("/{tag_id}", response_model=TagOut)
async def update_tag(
    tag_id:  uuid.UUID,
    payload: TagUpdate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    tag = await _load_tag(db, tag_id=tag_id, org_id=member.org_id)
    changed: dict[str, tuple[str, str]] = {}

    if payload.name is not None:
        try:
            new_name = svc_87.normalize_name(payload.name)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if new_name.lower() != tag.name.lower() and await _name_conflict(
            db, org_id=member.org_id, name=new_name, exclude_id=tag.id,
        ):
            raise HTTPException(
                status_code=409, detail="Tag name already in use",
            )
        if new_name != tag.name:
            changed["name"] = (tag.name, new_name)
            tag.name = new_name

    if payload.color is not None:
        try:
            new_color = svc_87.normalize_color(payload.color)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if new_color != tag.color:
            changed["color"] = (tag.color, new_color)
            tag.color = new_color

    if changed:
        tag.updated_at = datetime.now(UTC)

    await log_action(
        db,
        action="invoice_tag.updated",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="invoice_tag",
        target_id=str(tag.id),
        request=request,
        extra={"changed": {k: {"from": v[0], "to": v[1]} for k, v in changed.items()}},
    )
    await db.commit()
    await db.refresh(tag)
    return await _to_out(db, tag)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id:  uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    tag = await _load_tag(db, tag_id=tag_id, org_id=member.org_id)
    assignments = await _count_invoices(db, tag_id=tag.id)
    name_snapshot = tag.name
    await db.delete(tag)
    await log_action(
        db,
        action="invoice_tag.deleted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="invoice_tag",
        target_id=str(tag_id),
        request=request,
        extra={"name": name_snapshot, "assignments_removed": assignments},
    )
    await db.commit()


# ── tag → invoices ──────────────────────────────────────────────────────


@router.get("/{tag_id}/invoices", response_model=list[InvoiceRef])
async def list_invoices_for_tag(
    tag_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    await _load_tag(db, tag_id=tag_id, org_id=member.org_id)
    rows = (await db.execute(
        select(Invoice.id, Invoice.invoice_number)
        .join(
            InvoiceTagAssignment,
            InvoiceTagAssignment.invoice_id == Invoice.id,
        )
        .where(
            InvoiceTagAssignment.tag_id == tag_id,
            Invoice.org_id == member.org_id,
        )
        .order_by(Invoice.invoice_number)
    )).all()
    return [InvoiceRef(id=r[0], invoice_number=r[1]) for r in rows]


@router.get("/invoices/{invoice_id}", response_model=list[TagOut])
async def list_tags_for_invoice(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    await _load_invoice(
        db, invoice_id=invoice_id, org_id=member.org_id,
    )
    rows = (await db.scalars(
        select(InvoiceTag)
        .join(
            InvoiceTagAssignment,
            InvoiceTagAssignment.tag_id == InvoiceTag.id,
        )
        .where(
            InvoiceTagAssignment.invoice_id == invoice_id,
            InvoiceTag.org_id == member.org_id,
        )
        .order_by(func.lower(InvoiceTag.name))
    )).all()
    return [await _to_out(db, r) for r in rows]


# ── assignments ─────────────────────────────────────────────────────────


@router.post("/assignments", status_code=status.HTTP_201_CREATED)
async def assign_tag(
    payload: AssignmentIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    # Both ends must belong to the caller's org; either mismatch
    # is a 404 (don't leak foreign existence).
    await _load_invoice(
        db, invoice_id=payload.invoice_id, org_id=member.org_id,
    )
    await _load_tag(db, tag_id=payload.tag_id, org_id=member.org_id)

    # Idempotent — re-assigning an existing pair is a no-op.
    existing = await db.scalar(
        select(InvoiceTagAssignment).where(
            InvoiceTagAssignment.invoice_id == payload.invoice_id,
            InvoiceTagAssignment.tag_id == payload.tag_id,
        )
    )
    if existing is not None:
        return {"status": "already_assigned"}

    current = await db.scalar(
        select(func.count()).select_from(InvoiceTagAssignment)
        .where(InvoiceTagAssignment.invoice_id == payload.invoice_id)
    )
    try:
        svc_87.assert_under_limit(current_count=int(current or 0))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.add(InvoiceTagAssignment(
        invoice_id=payload.invoice_id,
        tag_id=payload.tag_id,
        assigned_by_user_id=user["user_id"],
    ))
    await log_action(
        db,
        action="invoice_tag.assigned",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="invoice",
        target_id=str(payload.invoice_id),
        request=request,
        extra={"tag_id": str(payload.tag_id)},
    )
    await db.commit()
    return {"status": "assigned"}


@router.delete("/assignments", status_code=status.HTTP_204_NO_CONTENT)
async def unassign_tag(
    payload: AssignmentIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    await _load_invoice(
        db, invoice_id=payload.invoice_id, org_id=member.org_id,
    )
    await _load_tag(db, tag_id=payload.tag_id, org_id=member.org_id)

    await db.execute(
        delete(InvoiceTagAssignment).where(
            InvoiceTagAssignment.invoice_id == payload.invoice_id,
            InvoiceTagAssignment.tag_id == payload.tag_id,
        )
    )
    await log_action(
        db,
        action="invoice_tag.unassigned",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="invoice",
        target_id=str(payload.invoice_id),
        request=request,
        extra={"tag_id": str(payload.tag_id)},
    )
    await db.commit()
