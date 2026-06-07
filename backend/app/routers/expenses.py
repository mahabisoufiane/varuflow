"""Expense tracking router (Item 43).

Endpoints under ``/api/expenses``:

* ``GET    /categories``               — list categories (seeds defaults).
* ``POST   /categories``               — create a category (owner/admin only).
* ``PATCH  /categories/{id}``          — rename / recolor / remap to SIE.
* ``DELETE /categories/{id}``          — delete; expenses are de-categorised.
* ``GET    /``                         — list expenses (staff see own only).
* ``POST   /``                         — log an expense (auto-seeds categories).
* ``GET    /{id}``                     — expense detail.
* ``PATCH  /{id}``                     — edit a DRAFT expense.
* ``DELETE /{id}``                     — delete (owner/admin or submitter of DRAFT).
* ``POST   /{id}/approve``             — owner/admin approves a DRAFT.
* ``POST   /{id}/reject``              — owner/admin rejects with a note.
* ``POST   /{id}/resubmit``            — submitter flips REJECTED → DRAFT.
* ``POST   /{id}/receipt``             — attach an uploaded receipt URL.
* ``GET    /export.csv``               — CSV export (audits ``expense.exported``).
* ``GET    /analytics/by-category``    — aggregated totals per category.

All mutations audit via :func:`log_action`.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
import math
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.expenses import Expense, ExpenseCategory, ExpenseStatus
from app.models.organization import OrgRole
from app.services import expense_service as svc
from app.services.audit import log_action

router = APIRouter(prefix="/api/expenses", tags=["expenses"], dependencies=[Depends(require_module("finance"))])


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _member(ctx: tuple):
    _, member = ctx
    return member


def _actor(ctx: tuple) -> uuid.UUID | None:
    user, _ = ctx
    uid = user.get("user_id")
    if isinstance(uid, uuid.UUID):
        return uid
    try:
        return uuid.UUID(str(uid))
    except Exception:
        return None


def _is_owner_or_admin(ctx: tuple) -> bool:
    m = _member(ctx)
    return m.role in (OrgRole.OWNER, OrgRole.ADMIN)


def _require_owner_or_admin(ctx: tuple) -> None:
    if not _is_owner_or_admin(ctx):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="only_owner_or_admin",
        )


# ═══════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════


class CategoryIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    color: str = Field(default="#64748b", pattern=r"^#[0-9A-Fa-f]{6}$")
    sie_account: str | None = Field(default=None, max_length=10)
    is_default: bool = False


class CategoryUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    sie_account: str | None = Field(default=None, max_length=10)
    is_default: bool | None = None


class CategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    color: str
    sie_account: str | None
    is_default: bool


class ExpenseCreateIn(BaseModel):
    category_id: uuid.UUID | None = None
    amount: Decimal
    currency: str = Field(default="SEK")
    description: str | None = None
    expense_date: date
    supplier_id: uuid.UUID | None = None
    receipt_url: str | None = Field(default=None, max_length=2048)
    receipt_mime: str | None = Field(default=None, max_length=120)
    receipt_size: int | None = None

    @field_validator("amount")
    @classmethod
    def _amount(cls, v):
        return svc.validate_amount(v)

    @field_validator("currency")
    @classmethod
    def _currency(cls, v):
        return svc.validate_currency(v)


class ExpenseUpdateIn(BaseModel):
    category_id: uuid.UUID | None = None
    amount: Decimal | None = None
    currency: str | None = None
    description: str | None = None
    expense_date: date | None = None
    supplier_id: uuid.UUID | None = None

    @field_validator("amount")
    @classmethod
    def _amount(cls, v):
        if v is None:
            return v
        return svc.validate_amount(v)

    @field_validator("currency")
    @classmethod
    def _currency(cls, v):
        if v is None:
            return v
        return svc.validate_currency(v)


class ReceiptIn(BaseModel):
    receipt_url: str = Field(..., max_length=2048)
    receipt_mime: str | None = Field(default=None, max_length=120)
    receipt_size: int | None = None


class RejectIn(BaseModel):
    note: str = Field(..., min_length=1, max_length=1000)


class ExpenseOut(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID | None
    amount: Decimal
    currency: str
    description: str | None
    expense_date: date
    receipt_url: str | None
    receipt_mime: str | None
    receipt_size: int | None
    status: str
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    review_note: str | None
    supplier_id: uuid.UUID | None
    created_by: uuid.UUID | None
    created_at: datetime

    @classmethod
    def from_row(cls, row: Expense) -> "ExpenseOut":
        return cls(
            id=row.id,
            category_id=row.category_id,
            amount=row.amount,
            currency=row.currency,
            description=row.description,
            expense_date=row.expense_date,
            receipt_url=row.receipt_url,
            receipt_mime=row.receipt_mime,
            receipt_size=row.receipt_size,
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
            approved_by=row.approved_by,
            approved_at=row.approved_at,
            review_note=row.review_note,
            supplier_id=row.supplier_id,
            created_by=row.created_by,
            created_at=row.created_at,
        )


class CategoryTotalOut(BaseModel):
    category_id: uuid.UUID | None
    category_name: str
    category_color: str
    total: Decimal
    count: int


# ═══════════════════════════════════════════════════════════════════
# Loaders
# ═══════════════════════════════════════════════════════════════════


async def _load_category(
    db: AsyncSession, *, cid: uuid.UUID, org_id: uuid.UUID,
) -> ExpenseCategory:
    row = await db.scalar(
        select(ExpenseCategory).where(
            ExpenseCategory.id == cid, ExpenseCategory.org_id == org_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="category_not_found")
    return row


async def _load_expense(
    db: AsyncSession, *, eid: uuid.UUID, org_id: uuid.UUID,
) -> Expense:
    row = await db.scalar(
        select(Expense).where(
            Expense.id == eid, Expense.org_id == org_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="expense_not_found")
    return row


async def _clear_default_category(
    db: AsyncSession, *, org_id: uuid.UUID, except_id: uuid.UUID | None = None,
) -> None:
    from sqlalchemy import update
    stmt = (
        update(ExpenseCategory)
        .where(
            ExpenseCategory.org_id == org_id,
            ExpenseCategory.is_default == True,  # noqa: E712
        )
        .values(is_default=False)
    )
    if except_id is not None:
        stmt = stmt.where(ExpenseCategory.id != except_id)
    await db.execute(stmt)


# ═══════════════════════════════════════════════════════════════════
# Category endpoints
# ═══════════════════════════════════════════════════════════════════


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    existing = (
        await db.execute(
            select(ExpenseCategory)
            .where(ExpenseCategory.org_id == org_id)
            .order_by(ExpenseCategory.is_default.desc(), ExpenseCategory.name.asc())
        )
    ).scalars().all()
    if not existing:
        # Lazy seed for a never-configured org so the UI picker isn't empty.
        existing = await svc.create_default_categories(db, org_id=org_id)
        await db.commit()
        existing = sorted(
            existing,
            key=lambda c: (0 if c.is_default else 1, c.name.lower()),
        )
    return [
        CategoryOut(
            id=c.id, name=c.name, color=c.color,
            sie_account=c.sie_account, is_default=c.is_default,
        )
        for c in existing
    ]


@router.post("/categories", response_model=CategoryOut, status_code=201)
async def create_category(
    body: CategoryIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _require_owner_or_admin(ctx)
    org_id = _org(ctx)

    if body.is_default:
        await _clear_default_category(db, org_id=org_id)

    row = ExpenseCategory(
        id=uuid.uuid4(),
        org_id=org_id,
        name=body.name.strip(),
        color=body.color,
        sie_account=body.sie_account,
        is_default=body.is_default,
    )
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="expense_category.created",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="expense_category",
        target_id=str(row.id),
        request=request,
        extra={"name": row.name},
    )
    await db.commit()
    return CategoryOut(
        id=row.id, name=row.name, color=row.color,
        sie_account=row.sie_account, is_default=row.is_default,
    )


@router.patch("/categories/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: uuid.UUID,
    body: CategoryUpdateIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _require_owner_or_admin(ctx)
    org_id = _org(ctx)
    row = await _load_category(db, cid=category_id, org_id=org_id)

    payload = body.model_dump(exclude_unset=True)
    if payload.get("is_default") is True:
        await _clear_default_category(db, org_id=org_id, except_id=row.id)
    for field in ("name", "color", "sie_account", "is_default"):
        if field in payload:
            value = payload[field]
            if field == "name" and isinstance(value, str):
                value = value.strip()
            setattr(row, field, value)

    await db.flush()
    await log_action(
        db,
        action="expense_category.updated",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="expense_category",
        target_id=str(row.id),
        request=request,
        extra={"fields": list(payload.keys())},
    )
    await db.commit()
    await db.refresh(row)
    return CategoryOut(
        id=row.id, name=row.name, color=row.color,
        sie_account=row.sie_account, is_default=row.is_default,
    )


@router.delete("/categories/{category_id}", status_code=204)
async def delete_category(
    category_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _require_owner_or_admin(ctx)
    org_id = _org(ctx)
    row = await _load_category(db, cid=category_id, org_id=org_id)
    await db.delete(row)
    await db.flush()
    await log_action(
        db,
        action="expense_category.deleted",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="expense_category",
        target_id=str(category_id),
        request=request,
        extra={"name": row.name},
    )
    await db.commit()


# ═══════════════════════════════════════════════════════════════════
# Expense endpoints
# ═══════════════════════════════════════════════════════════════════


def _scope_to_member(query, ctx):
    """Staff (MEMBER role) only see rows they created. Owners +
    admins see the whole org. Enforced in SQL so a crafted client
    cannot list another staff member's expenses."""
    m = _member(ctx)
    if m.role == OrgRole.MEMBER:
        actor = _actor(ctx)
        if actor is None:
            # Staff without a resolvable user id sees nothing — safer
            # than leaking the whole org while we figure out the id.
            query = query.where(Expense.created_by == uuid.UUID(int=0))
        else:
            query = query.where(Expense.created_by == actor)
    return query


@router.get("")
async def list_expenses(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    category_id: uuid.UUID | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    org_id = _org(ctx)
    q = select(Expense).where(Expense.org_id == org_id)
    q = _scope_to_member(q, ctx)
    if category_id is not None:
        q = q.where(Expense.category_id == category_id)
    if status_:
        try:
            q = q.where(Expense.status == ExpenseStatus(status_.upper()))
        except ValueError:
            raise HTTPException(status_code=422, detail="invalid_status")
    if date_from is not None:
        q = q.where(Expense.expense_date >= date_from)
    if date_to is not None:
        q = q.where(Expense.expense_date <= date_to)

    # Count total matching rows.
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    total_pages = math.ceil(total / limit) if total > 0 else 1

    q = q.order_by(Expense.expense_date.desc(), Expense.created_at.desc())
    q = q.offset((page - 1) * limit).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return {
        "items": [ExpenseOut.from_row(r) for r in rows],
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


@router.post("", response_model=ExpenseOut, status_code=201)
async def create_expense(
    body: ExpenseCreateIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)

    if body.category_id is not None:
        # Verify the category belongs to this org.
        await _load_category(db, cid=body.category_id, org_id=org_id)

    if body.receipt_url or body.receipt_mime or body.receipt_size:
        try:
            svc.validate_receipt(body.receipt_mime, body.receipt_size)
        except svc.ReceiptError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    row = Expense(
        id=uuid.uuid4(),
        org_id=org_id,
        created_by=_actor(ctx),
        category_id=body.category_id,
        amount=body.amount,
        currency=body.currency,
        description=body.description,
        expense_date=body.expense_date,
        supplier_id=body.supplier_id,
        receipt_url=body.receipt_url,
        receipt_mime=body.receipt_mime,
        receipt_size=body.receipt_size,
        status=ExpenseStatus.DRAFT,
    )
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="expense.created",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="expense",
        target_id=str(row.id),
        request=request,
        extra={"amount": str(row.amount), "currency": row.currency},
    )
    await db.commit()
    await db.refresh(row)
    return ExpenseOut.from_row(row)


@router.get("/{expense_id}", response_model=ExpenseOut)
async def get_expense(
    expense_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    row = await _load_expense(db, eid=expense_id, org_id=org_id)
    # Staff can only view their own rows.
    m = _member(ctx)
    if m.role == OrgRole.MEMBER and row.created_by != _actor(ctx):
        raise HTTPException(status_code=404, detail="expense_not_found")
    return ExpenseOut.from_row(row)


@router.patch("/{expense_id}", response_model=ExpenseOut)
async def update_expense(
    expense_id: uuid.UUID,
    body: ExpenseUpdateIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    row = await _load_expense(db, eid=expense_id, org_id=org_id)

    m = _member(ctx)
    if m.role == OrgRole.MEMBER and row.created_by != _actor(ctx):
        raise HTTPException(status_code=404, detail="expense_not_found")
    if row.status == ExpenseStatus.APPROVED:
        raise HTTPException(status_code=400, detail="expense_locked")

    payload = body.model_dump(exclude_unset=True)
    if "category_id" in payload and payload["category_id"] is not None:
        await _load_category(db, cid=payload["category_id"], org_id=org_id)

    for field in (
        "category_id", "amount", "currency", "description",
        "expense_date", "supplier_id",
    ):
        if field in payload:
            setattr(row, field, payload[field])

    # If a rejected expense was edited, flip it back to DRAFT so the
    # reviewer sees it in the pending queue again.
    if row.status == ExpenseStatus.REJECTED:
        row.status = ExpenseStatus.DRAFT
        row.review_note = None

    await db.flush()
    await log_action(
        db,
        action="expense.updated",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="expense",
        target_id=str(row.id),
        request=request,
        extra={"fields": list(payload.keys())},
    )
    await db.commit()
    await db.refresh(row)
    return ExpenseOut.from_row(row)


@router.delete("/{expense_id}", status_code=204)
async def delete_expense(
    expense_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    row = await _load_expense(db, eid=expense_id, org_id=org_id)
    m = _member(ctx)
    if m.role == OrgRole.MEMBER:
        if row.created_by != _actor(ctx):
            raise HTTPException(status_code=404, detail="expense_not_found")
        # Staff can only bin their own drafts; once approved the row
        # is part of the accounting record and only an owner/admin
        # can remove it.
        if row.status != ExpenseStatus.DRAFT:
            raise HTTPException(status_code=403, detail="cannot_delete_reviewed")
    await db.delete(row)
    await db.flush()
    await log_action(
        db,
        action="expense.deleted",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="expense",
        target_id=str(expense_id),
        request=request,
        extra={"amount": str(row.amount), "status": row.status.value},
    )
    await db.commit()


@router.post("/{expense_id}/approve", response_model=ExpenseOut)
async def approve_expense(
    expense_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _require_owner_or_admin(ctx)
    org_id = _org(ctx)
    row = await _load_expense(db, eid=expense_id, org_id=org_id)
    try:
        svc.assert_transition(row.status.value, ExpenseStatus.APPROVED.value)
    except svc.ApprovalError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    row.status = ExpenseStatus.APPROVED
    row.approved_by = _actor(ctx)
    row.approved_at = svc.now_utc()
    row.review_note = None
    await db.flush()
    await log_action(
        db,
        action="expense.approved",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="expense",
        target_id=str(row.id),
        request=request,
    )
    await db.commit()
    await db.refresh(row)
    return ExpenseOut.from_row(row)


@router.post("/{expense_id}/reject", response_model=ExpenseOut)
async def reject_expense(
    expense_id: uuid.UUID,
    body: RejectIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _require_owner_or_admin(ctx)
    org_id = _org(ctx)
    row = await _load_expense(db, eid=expense_id, org_id=org_id)
    try:
        svc.assert_transition(row.status.value, ExpenseStatus.REJECTED.value)
    except svc.ApprovalError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    row.status = ExpenseStatus.REJECTED
    row.review_note = body.note.strip()
    row.approved_by = _actor(ctx)
    row.approved_at = svc.now_utc()
    await db.flush()
    await log_action(
        db,
        action="expense.rejected",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="expense",
        target_id=str(row.id),
        request=request,
        extra={"note": row.review_note},
    )
    await db.commit()
    await db.refresh(row)
    return ExpenseOut.from_row(row)


@router.post("/{expense_id}/resubmit", response_model=ExpenseOut)
async def resubmit_expense(
    expense_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    row = await _load_expense(db, eid=expense_id, org_id=org_id)
    m = _member(ctx)
    # Submitter resubmits their own rejected row; owner/admin can
    # re-open any rejected row on behalf of the submitter.
    if m.role == OrgRole.MEMBER and row.created_by != _actor(ctx):
        raise HTTPException(status_code=404, detail="expense_not_found")
    try:
        svc.assert_transition(row.status.value, ExpenseStatus.DRAFT.value)
    except svc.ApprovalError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    row.status = ExpenseStatus.DRAFT
    row.review_note = None
    row.approved_by = None
    row.approved_at = None
    await db.flush()
    await log_action(
        db,
        action="expense.resubmitted",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="expense",
        target_id=str(row.id),
        request=request,
    )
    await db.commit()
    await db.refresh(row)
    return ExpenseOut.from_row(row)


@router.post("/{expense_id}/receipt", response_model=ExpenseOut)
async def attach_receipt(
    expense_id: uuid.UUID,
    body: ReceiptIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Record a receipt URL against an expense.

    The actual upload happens via the tenant's object-store SDK on
    the client (presigned URL). This endpoint just records the
    final URL + metadata so the PDF / CSV exporters and the review
    UI have a handle to the artifact.

    Mobile receipt capture flow: the phone app opens the camera,
    uploads the captured image directly to S3, then POSTs the
    resulting URL here with a ``receipt_mime`` of ``image/jpeg``.
    """
    org_id = _org(ctx)
    row = await _load_expense(db, eid=expense_id, org_id=org_id)
    m = _member(ctx)
    if m.role == OrgRole.MEMBER and row.created_by != _actor(ctx):
        raise HTTPException(status_code=404, detail="expense_not_found")
    if row.status == ExpenseStatus.APPROVED:
        raise HTTPException(status_code=400, detail="expense_locked")

    try:
        svc.validate_receipt(body.receipt_mime, body.receipt_size)
    except svc.ReceiptError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    row.receipt_url = body.receipt_url
    row.receipt_mime = body.receipt_mime
    row.receipt_size = body.receipt_size
    await db.flush()
    await log_action(
        db,
        action="expense.receipt_attached",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="expense",
        target_id=str(row.id),
        request=request,
        extra={"mime": body.receipt_mime, "size": body.receipt_size},
    )
    await db.commit()
    await db.refresh(row)
    return ExpenseOut.from_row(row)


# ═══════════════════════════════════════════════════════════════════
# Export + analytics
# ═══════════════════════════════════════════════════════════════════


async def _rows_for_export(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    date_from: date | None,
    date_to: date | None,
) -> list[dict]:
    from sqlalchemy.orm import aliased

    cat = aliased(ExpenseCategory)
    stmt = (
        select(
            Expense.id,
            Expense.expense_date,
            Expense.amount,
            Expense.currency,
            Expense.description,
            Expense.status,
            Expense.receipt_url,
            Expense.created_by,
            Expense.category_id,
            cat.name.label("category_name"),
            cat.color.label("category_color"),
            cat.sie_account.label("sie_account"),
        )
        .join(cat, cat.id == Expense.category_id, isouter=True)
        .where(Expense.org_id == org_id)
        .order_by(Expense.expense_date.desc())
    )
    if date_from is not None:
        stmt = stmt.where(Expense.expense_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Expense.expense_date <= date_to)
    res = await db.execute(stmt)
    out: list[dict] = []
    for r in res.all():
        out.append({
            "id": r.id,
            "expense_date": r.expense_date,
            "amount": r.amount,
            "currency": r.currency,
            "description": r.description,
            "status": (r.status.value if hasattr(r.status, "value") else str(r.status)),
            "receipt_url": r.receipt_url,
            "created_by": r.created_by,
            "category_id": r.category_id,
            "category_name": r.category_name,
            "category_color": r.category_color,
            "sie_account": r.sie_account,
        })
    return out


@router.get("/export.csv")
async def export_csv(
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    _require_owner_or_admin(ctx)
    org_id = _org(ctx)
    rows = await _rows_for_export(
        db, org_id=org_id, date_from=date_from, date_to=date_to,
    )
    body = svc.build_expenses_csv(rows)
    await log_action(
        db,
        action="expense.exported",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="expense_export",
        target_id=None,
        request=request,
        extra={"rows": len(rows)},
    )
    await db.commit()
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="expenses.csv"'},
    )


@router.get("/analytics/by-category", response_model=list[CategoryTotalOut])
async def analytics_by_category(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
):
    """Analytics endpoint consumed by the /analytics overview and
    the expenses page. Staff only see their own numbers; owners +
    admins see the whole org (same scoping as the list endpoint)."""
    org_id = _org(ctx)
    rows = await _rows_for_export(
        db, org_id=org_id, date_from=date_from, date_to=date_to,
    )
    # Staff-scope the aggregated list in Python so the same SQL
    # query serves both the CSV export and the analytics breakdown.
    m = _member(ctx)
    if m.role == OrgRole.MEMBER:
        actor = _actor(ctx)
        rows = [r for r in rows if r.get("created_by") == actor]
    totals = svc.group_by_category(rows)
    return [CategoryTotalOut(**t.to_dict()) for t in totals]
