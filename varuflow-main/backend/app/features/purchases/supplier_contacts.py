"""Supplier contacts router (Item 78).

Endpoints under ``/api/supplier-contacts``:

    GET    ?supplier_id=...     list all contacts for a supplier
    POST   ""                   create a contact
    GET    /{contact_id}        detail
    PATCH  /{contact_id}        edit
    DELETE /{contact_id}        delete
    POST   /{contact_id}/primary  make this contact the primary
                                  (demotes any existing primary)

Every mutation emits one audit entry (``supplier_contact.created /
updated / deleted / promoted``) with ``request=request``. Primary-
contact uniqueness is enforced both in Python (the
``/primary`` endpoint demotes the old primary in the same
transaction) and at the DB level (partial unique index over
``supplier_id`` WHERE ``is_primary = true``).
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.features.inventory.models import Supplier
from .supplier_contact import SupplierContact
from app.services import supplier_contact as svc_78
from app.services.audit import log_action
from app.middleware.plan_check import require_module

router = APIRouter(
    prefix="/api/supplier-contacts", tags=["supplier-contacts"],
    dependencies=[Depends(require_module("inventory"))],
)

log = logging.getLogger(__name__)


# ── bodies ──────────────────────────────────────────────────────────────


class ContactCreate(BaseModel):
    supplier_id:   uuid.UUID
    name:          str
    role:          str | None = None
    email:         str | None = None
    phone:         str | None = None
    is_primary:    bool = False
    receives_rfq:  bool = True


class ContactUpdate(BaseModel):
    name:          str | None = None
    role:          str | None = None
    email:         str | None = None
    phone:         str | None = None
    receives_rfq:  bool | None = None


class ContactOut(BaseModel):
    id:            uuid.UUID
    supplier_id:   uuid.UUID
    name:          str
    role:          str | None
    email:         str | None
    phone:         str | None
    is_primary:    bool
    receives_rfq:  bool
    created_at:    datetime
    updated_at:    datetime


# ── helpers ─────────────────────────────────────────────────────────────


async def _load_supplier(
    db: AsyncSession, *, supplier_id: uuid.UUID, org_id: uuid.UUID,
) -> Supplier:
    row = await db.scalar(
        select(Supplier).where(Supplier.id == supplier_id)
    )
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return row


async def _load_contact(
    db: AsyncSession, *, contact_id: uuid.UUID, org_id: uuid.UUID,
) -> SupplierContact:
    row = await db.scalar(
        select(SupplierContact).where(SupplierContact.id == contact_id)
    )
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Contact not found")
    return row


async def _demote_other_primaries(
    db: AsyncSession,
    *,
    supplier_id: uuid.UUID,
    org_id: uuid.UUID,
    keep_id: uuid.UUID | None,
) -> int:
    """Set ``is_primary=False`` for every other row on this supplier."""
    stmt = (
        update(SupplierContact)
        .where(
            SupplierContact.supplier_id == supplier_id,
            SupplierContact.org_id == org_id,
            SupplierContact.is_primary.is_(True),
        )
        .values(is_primary=False, updated_at=datetime.now(UTC))
    )
    if keep_id is not None:
        stmt = stmt.where(SupplierContact.id != keep_id)
    result = await db.execute(stmt)
    return result.rowcount or 0


def _to_out(row: SupplierContact) -> ContactOut:
    return ContactOut(
        id=row.id, supplier_id=row.supplier_id,
        name=row.name, role=row.role,
        email=row.email, phone=row.phone,
        is_primary=row.is_primary,
        receives_rfq=row.receives_rfq,
        created_at=row.created_at, updated_at=row.updated_at,
    )


# ── endpoints ───────────────────────────────────────────────────────────


@router.get("", response_model=list[ContactOut])
async def list_contacts(
    supplier_id: uuid.UUID = Query(...),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    # Verify the supplier belongs to the caller before echoing rows.
    await _load_supplier(db, supplier_id=supplier_id, org_id=member.org_id)
    rows = (await db.scalars(
        select(SupplierContact)
        .where(
            SupplierContact.org_id == member.org_id,
            SupplierContact.supplier_id == supplier_id,
        )
        # Primary first, then newest by created_at, then name for
        # deterministic order on ties.
        .order_by(
            SupplierContact.is_primary.desc(),
            SupplierContact.created_at.desc(),
            func.lower(SupplierContact.name),
        )
    )).all()
    return [_to_out(r) for r in rows]


@router.post(
    "", response_model=ContactOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_contact(
    payload: ContactCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    await _load_supplier(
        db, supplier_id=payload.supplier_id, org_id=member.org_id,
    )

    try:
        name  = svc_78.normalize_name(payload.name)
        role  = svc_78.normalize_role(payload.role)
        email = svc_78.normalize_email(payload.email)
        phone = svc_78.normalize_phone(payload.phone)
        svc_78.assert_has_channel(email=email, phone=phone)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    current = await db.scalar(
        select(func.count()).select_from(SupplierContact).where(
            SupplierContact.supplier_id == payload.supplier_id,
        )
    )
    try:
        svc_78.assert_under_limit(current_count=int(current or 0))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    contact = SupplierContact(
        id=uuid.uuid4(),
        org_id=member.org_id,
        supplier_id=payload.supplier_id,
        name=name,
        role=role,
        email=email,
        phone=phone,
        is_primary=payload.is_primary,
        receives_rfq=payload.receives_rfq,
    )

    if payload.is_primary:
        # Demote any existing primary *before* inserting so the
        # partial unique index doesn't fire.
        await _demote_other_primaries(
            db, supplier_id=payload.supplier_id,
            org_id=member.org_id, keep_id=None,
        )

    db.add(contact)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A primary contact already exists for this supplier",
        )

    await log_action(
        db,
        action="supplier_contact.created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="supplier_contact",
        target_id=str(contact.id),
        request=request,
        extra={
            "supplier_id": str(payload.supplier_id),
            "name":        contact.name,
            "is_primary":  contact.is_primary,
        },
    )
    await db.commit()
    await db.refresh(contact)
    return _to_out(contact)


@router.get("/{contact_id}", response_model=ContactOut)
async def get_contact(
    contact_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    row = await _load_contact(
        db, contact_id=contact_id, org_id=member.org_id,
    )
    return _to_out(row)


@router.patch("/{contact_id}", response_model=ContactOut)
async def update_contact(
    contact_id: uuid.UUID,
    payload:    ContactUpdate,
    request:    Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load_contact(
        db, contact_id=contact_id, org_id=member.org_id,
    )
    changed: list[str] = []

    try:
        if payload.name is not None:
            new_name = svc_78.normalize_name(payload.name)
            if new_name != row.name:
                row.name = new_name
                changed.append("name")
        if payload.role is not None:
            new_role = svc_78.normalize_role(payload.role)
            if new_role != row.role:
                row.role = new_role
                changed.append("role")
        if payload.email is not None:
            new_email = svc_78.normalize_email(payload.email)
            if new_email != row.email:
                row.email = new_email
                changed.append("email")
        if payload.phone is not None:
            new_phone = svc_78.normalize_phone(payload.phone)
            if new_phone != row.phone:
                row.phone = new_phone
                changed.append("phone")
        # Invariant: post-update the row must still have a channel.
        svc_78.assert_has_channel(email=row.email, phone=row.phone)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if payload.receives_rfq is not None and (
        payload.receives_rfq != row.receives_rfq
    ):
        row.receives_rfq = payload.receives_rfq
        changed.append("receives_rfq")

    if changed:
        row.updated_at = datetime.now(UTC)

    await log_action(
        db,
        action="supplier_contact.updated",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="supplier_contact",
        target_id=str(row.id),
        request=request,
        extra={"changed": changed},
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: uuid.UUID,
    request:    Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load_contact(
        db, contact_id=contact_id, org_id=member.org_id,
    )
    snapshot = {
        "supplier_id": str(row.supplier_id),
        "was_primary": row.is_primary,
    }
    await db.delete(row)
    await log_action(
        db,
        action="supplier_contact.deleted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="supplier_contact",
        target_id=str(contact_id),
        request=request,
        extra=snapshot,
    )
    await db.commit()


@router.post("/{contact_id}/primary", response_model=ContactOut)
async def make_primary(
    contact_id: uuid.UUID,
    request:    Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load_contact(
        db, contact_id=contact_id, org_id=member.org_id,
    )

    if row.is_primary:
        # Already primary — no-op, but still audit for traceability.
        await log_action(
            db,
            action="supplier_contact.promoted",
            org_id=member.org_id,
            actor_user_id=user["user_id"],
            target_type="supplier_contact",
            target_id=str(row.id),
            request=request,
            extra={"no_op": True, "supplier_id": str(row.supplier_id)},
        )
        await db.commit()
        return _to_out(row)

    # Demote every other primary on the same supplier first.
    demoted = await _demote_other_primaries(
        db,
        supplier_id=row.supplier_id,
        org_id=member.org_id,
        keep_id=row.id,
    )
    row.is_primary = True
    row.updated_at = datetime.now(UTC)

    await log_action(
        db,
        action="supplier_contact.promoted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="supplier_contact",
        target_id=str(row.id),
        request=request,
        extra={
            "supplier_id":   str(row.supplier_id),
            "demoted_count": demoted,
        },
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)
