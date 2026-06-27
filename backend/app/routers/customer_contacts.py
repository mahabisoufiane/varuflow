"""Customer contacts router (Item 74).

Endpoints under ``/api/customer-contacts``:

    GET    ?customer_id=...     list all contacts for a customer
    POST   ""                   create a contact
    GET    /{contact_id}        detail
    PATCH  /{contact_id}        edit
    DELETE /{contact_id}        delete
    POST   /{contact_id}/primary  make this contact the primary
                                  (demotes any existing primary)

Every mutation emits one audit entry (``customer_contact.created /
updated / deleted / promoted``) with ``request=request``. Primary-
contact uniqueness is enforced both in Python (the
``/primary`` endpoint demotes the old primary in the same
transaction) and at the DB level (partial unique index over
``customer_id`` WHERE ``is_primary = true``).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.customer_contact import CustomerContact
from app.models.invoicing import Customer
from app.services import customer_contact as svc_74
from app.services.audit import log_action

router = APIRouter(
    prefix="/api/customer-contacts", tags=["customer-contacts"],
)

log = logging.getLogger(__name__)


# ── bodies ──────────────────────────────────────────────────────────────


class ContactCreate(BaseModel):
    customer_id:      uuid.UUID
    name:             str
    role:             str | None = None
    email:            str | None = None
    phone:            str | None = None
    is_primary:       bool = False
    receives_dunning: bool = True


class ContactUpdate(BaseModel):
    name:             str | None = None
    role:             str | None = None
    email:            str | None = None
    phone:            str | None = None
    receives_dunning: bool | None = None


class ContactOut(BaseModel):
    id:               uuid.UUID
    customer_id:      uuid.UUID
    name:             str
    role:             str | None
    email:            str | None
    phone:            str | None
    is_primary:       bool
    receives_dunning: bool
    created_at:       datetime
    updated_at:       datetime


# ── helpers ─────────────────────────────────────────────────────────────


async def _load_customer(
    db: AsyncSession, *, customer_id: uuid.UUID, org_id: uuid.UUID,
) -> Customer:
    row = await db.scalar(
        select(Customer).where(Customer.id == customer_id)
    )
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Customer not found")
    return row


async def _load_contact(
    db: AsyncSession, *, contact_id: uuid.UUID, org_id: uuid.UUID,
) -> CustomerContact:
    row = await db.scalar(
        select(CustomerContact).where(CustomerContact.id == contact_id)
    )
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Contact not found")
    return row


async def _demote_other_primaries(
    db: AsyncSession,
    *,
    customer_id: uuid.UUID,
    org_id: uuid.UUID,
    keep_id: uuid.UUID | None,
) -> int:
    """Set ``is_primary=False`` for every other row on this customer."""
    stmt = (
        update(CustomerContact)
        .where(
            CustomerContact.customer_id == customer_id,
            CustomerContact.org_id == org_id,
            CustomerContact.is_primary.is_(True),
        )
        .values(is_primary=False, updated_at=datetime.utcnow())
    )
    if keep_id is not None:
        stmt = stmt.where(CustomerContact.id != keep_id)
    result = await db.execute(stmt)
    return result.rowcount or 0


def _to_out(row: CustomerContact) -> ContactOut:
    return ContactOut(
        id=row.id, customer_id=row.customer_id,
        name=row.name, role=row.role,
        email=row.email, phone=row.phone,
        is_primary=row.is_primary,
        receives_dunning=row.receives_dunning,
        created_at=row.created_at, updated_at=row.updated_at,
    )


# ── endpoints ───────────────────────────────────────────────────────────


@router.get("", response_model=list[ContactOut])
async def list_contacts(
    customer_id: uuid.UUID = Query(...),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    # Verify the customer belongs to the caller before echoing rows.
    await _load_customer(db, customer_id=customer_id, org_id=member.org_id)
    rows = (await db.scalars(
        select(CustomerContact)
        .where(
            CustomerContact.org_id == member.org_id,
            CustomerContact.customer_id == customer_id,
        )
        # Primary first, then newest by created_at, then name for
        # deterministic order on ties.
        .order_by(
            CustomerContact.is_primary.desc(),
            CustomerContact.created_at.desc(),
            func.lower(CustomerContact.name),
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
    await _load_customer(
        db, customer_id=payload.customer_id, org_id=member.org_id,
    )

    try:
        name  = svc_74.normalize_name(payload.name)
        role  = svc_74.normalize_role(payload.role)
        email = svc_74.normalize_email(payload.email)
        phone = svc_74.normalize_phone(payload.phone)
        svc_74.assert_has_channel(email=email, phone=phone)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    current = await db.scalar(
        select(func.count()).select_from(CustomerContact).where(
            CustomerContact.customer_id == payload.customer_id,
        )
    )
    try:
        svc_74.assert_under_limit(current_count=int(current or 0))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    contact = CustomerContact(
        id=uuid.uuid4(),
        org_id=member.org_id,
        customer_id=payload.customer_id,
        name=name,
        role=role,
        email=email,
        phone=phone,
        is_primary=payload.is_primary,
        receives_dunning=payload.receives_dunning,
    )

    if payload.is_primary:
        # Demote any existing primary *before* inserting so the
        # partial unique index doesn't fire.
        await _demote_other_primaries(
            db, customer_id=payload.customer_id,
            org_id=member.org_id, keep_id=None,
        )

    db.add(contact)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A primary contact already exists for this customer",
        )

    await log_action(
        db,
        action="customer_contact.created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="customer_contact",
        target_id=str(contact.id),
        request=request,
        extra={
            "customer_id": str(payload.customer_id),
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
            new_name = svc_74.normalize_name(payload.name)
            if new_name != row.name:
                row.name = new_name
                changed.append("name")
        if payload.role is not None:
            new_role = svc_74.normalize_role(payload.role)
            if new_role != row.role:
                row.role = new_role
                changed.append("role")
        if payload.email is not None:
            new_email = svc_74.normalize_email(payload.email)
            if new_email != row.email:
                row.email = new_email
                changed.append("email")
        if payload.phone is not None:
            new_phone = svc_74.normalize_phone(payload.phone)
            if new_phone != row.phone:
                row.phone = new_phone
                changed.append("phone")
        # Invariant: post-update the row must still have a channel.
        svc_74.assert_has_channel(email=row.email, phone=row.phone)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if payload.receives_dunning is not None and (
        payload.receives_dunning != row.receives_dunning
    ):
        row.receives_dunning = payload.receives_dunning
        changed.append("receives_dunning")

    if changed:
        row.updated_at = datetime.utcnow()

    await log_action(
        db,
        action="customer_contact.updated",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="customer_contact",
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
        "customer_id": str(row.customer_id),
        "was_primary": row.is_primary,
    }
    await db.delete(row)
    await log_action(
        db,
        action="customer_contact.deleted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="customer_contact",
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
            action="customer_contact.promoted",
            org_id=member.org_id,
            actor_user_id=user["user_id"],
            target_type="customer_contact",
            target_id=str(row.id),
            request=request,
            extra={"no_op": True, "customer_id": str(row.customer_id)},
        )
        await db.commit()
        return _to_out(row)

    # Demote every other primary on the same customer first.
    demoted = await _demote_other_primaries(
        db,
        customer_id=row.customer_id,
        org_id=member.org_id,
        keep_id=row.id,
    )
    row.is_primary = True
    row.updated_at = datetime.utcnow()

    await log_action(
        db,
        action="customer_contact.promoted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="customer_contact",
        target_id=str(row.id),
        request=request,
        extra={
            "customer_id":        str(row.customer_id),
            "demoted_count":      demoted,
        },
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)
