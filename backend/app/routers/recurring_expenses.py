"""Recurring expense template router (Item 97).

Endpoints under ``/api/recurring-expenses``:

    GET    ""                     list templates
    POST   ""                     create a template
    GET    /{template_id}          detail
    PATCH  /{template_id}          edit
    DELETE /{template_id}          delete
    POST   /{template_id}/generate mint the next Expense manually
    POST   /{template_id}/pause    deactivate
    POST   /{template_id}/resume   reactivate
    GET    /{template_id}/preview  ?count=N upcoming dates

``generate`` creates exactly one `Expense` row from the template and
advances `next_due_date`. It is idempotent only in the weak sense that
repeated calls keep appending expenses — the router does not dedupe
by day. Callers (UI / scheduler) must gate on ``is_due`` /
``next_due_date <= today`` themselves.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date as _date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.expenses import Expense, ExpenseCategory, ExpenseStatus
from app.models.inventory import Supplier
from app.models.recurring_expense import (
    RecurringExpenseCadence, RecurringExpenseTemplate,
)
from app.services import recurring_expense as svc_97
from app.services.audit import log_action

router = APIRouter(
    prefix="/api/recurring-expenses", tags=["recurring-expenses"],
    dependencies=[Depends(require_module("finance"))],
)

log = logging.getLogger(__name__)


# ── request / response ──────────────────────────────────────────────────


class TemplateCreate(BaseModel):
    title:          str
    amount:         str
    currency:       str = "SEK"
    cadence:        str
    interval_count: int = 1
    start_date:     _date
    end_date:       _date | None = None
    description:    str | None = None
    category_id:    uuid.UUID | None = None
    supplier_id:    uuid.UUID | None = None


class TemplateUpdate(BaseModel):
    title:          str | None = None
    amount:         str | None = None
    currency:       str | None = None
    cadence:        str | None = None
    interval_count: int | None = None
    start_date:     _date | None = None
    end_date:       _date | None = None
    description:    str | None = None
    category_id:    uuid.UUID | None = None
    supplier_id:    uuid.UUID | None = None


class TemplateOut(BaseModel):
    id:                        uuid.UUID
    title:                     str
    amount:                    str
    currency:                  str
    cadence:                   str
    interval_count:            int
    start_date:                _date
    end_date:                  _date | None
    next_due_date:             _date
    last_generated_at:         datetime | None
    last_generated_expense_id: uuid.UUID | None
    generated_count:           int
    is_active:                 bool
    category_id:               uuid.UUID | None
    supplier_id:               uuid.UUID | None
    description:               str | None
    created_at:                datetime
    updated_at:                datetime


class GenerateOut(BaseModel):
    expense_id:     uuid.UUID
    next_due_date:  _date | None


class PreviewOut(BaseModel):
    dates: list[_date]


# ── helpers ─────────────────────────────────────────────────────────────


def _to_out(row: RecurringExpenseTemplate) -> TemplateOut:
    return TemplateOut(
        id=row.id,
        title=row.title,
        amount=str(row.amount),
        currency=row.currency,
        cadence=row.cadence.value if isinstance(row.cadence, RecurringExpenseCadence) else str(row.cadence),
        interval_count=row.interval_count,
        start_date=row.start_date,
        end_date=row.end_date,
        next_due_date=row.next_due_date,
        last_generated_at=row.last_generated_at,
        last_generated_expense_id=row.last_generated_expense_id,
        generated_count=row.generated_count,
        is_active=row.is_active,
        category_id=row.category_id,
        supplier_id=row.supplier_id,
        description=row.description,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _load(
    db: AsyncSession, *, template_id: uuid.UUID, org_id: uuid.UUID,
) -> RecurringExpenseTemplate:
    row = await db.get(RecurringExpenseTemplate, template_id)
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Template not found")
    return row


async def _assert_category_belongs(
    db: AsyncSession, *, category_id: uuid.UUID | None, org_id: uuid.UUID,
) -> None:
    if category_id is None:
        return
    found = await db.scalar(
        select(ExpenseCategory.id).where(
            ExpenseCategory.id == category_id,
            ExpenseCategory.org_id == org_id,
        )
    )
    if found is None:
        raise HTTPException(status_code=404, detail="Category not found")


async def _assert_supplier_belongs(
    db: AsyncSession, *, supplier_id: uuid.UUID | None, org_id: uuid.UUID,
) -> None:
    if supplier_id is None:
        return
    found = await db.scalar(
        select(Supplier.id).where(
            Supplier.id == supplier_id, Supplier.org_id == org_id,
        )
    )
    if found is None:
        raise HTTPException(status_code=404, detail="Supplier not found")


# ── endpoints ───────────────────────────────────────────────────────────


@router.get("", response_model=list[TemplateOut])
async def list_templates(
    active_only: bool = Query(default=False),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    stmt = select(RecurringExpenseTemplate).where(
        RecurringExpenseTemplate.org_id == member.org_id,
    )
    if active_only:
        stmt = stmt.where(RecurringExpenseTemplate.is_active.is_(True))
    stmt = stmt.order_by(
        RecurringExpenseTemplate.is_active.desc(),
        RecurringExpenseTemplate.next_due_date.asc(),
    )
    rows = (await db.scalars(stmt)).all()
    return [_to_out(r) for r in rows]


@router.post(
    "", response_model=TemplateOut, status_code=status.HTTP_201_CREATED,
)
async def create_template(
    body:    TemplateCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    try:
        title    = svc_97.validate_title(body.title)
        amount   = svc_97.validate_amount(body.amount)
        currency = svc_97.validate_currency(body.currency)
        cadence  = svc_97.validate_cadence(body.cadence)
        interval = svc_97.validate_interval(body.interval_count)
        start, end = svc_97.validate_dates(
            start_date=body.start_date, end_date=body.end_date,
        )
        description = svc_97.validate_description(body.description)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await _assert_category_belongs(
        db, category_id=body.category_id, org_id=member.org_id,
    )
    await _assert_supplier_belongs(
        db, supplier_id=body.supplier_id, org_id=member.org_id,
    )

    next_due = svc_97.compute_next_due(
        start_date=start, cadence=cadence, interval=interval,
        last_generated=None, end_date=end,
    )
    if next_due is None:
        raise HTTPException(
            status_code=400,
            detail="schedule ends before any occurrence",
        )

    row = RecurringExpenseTemplate(
        org_id=member.org_id,
        created_by_user_id=uuid.UUID(user["user_id"]),
        title=title,
        category_id=body.category_id,
        supplier_id=body.supplier_id,
        amount=amount,
        currency=currency,
        description=description,
        cadence=RecurringExpenseCadence(cadence),
        interval_count=interval,
        start_date=start,
        end_date=end,
        next_due_date=next_due,
        is_active=True,
    )
    db.add(row)
    await db.flush()

    await log_action(
        db,
        action="recurring_expense.created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="recurring_expense_template",
        target_id=str(row.id),
        request=request,
        extra={"title": title, "cadence": cadence, "interval": interval},
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.get("/{template_id}", response_model=TemplateOut)
async def get_template(
    template_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    row = await _load(db, template_id=template_id, org_id=member.org_id)
    return _to_out(row)


@router.patch("/{template_id}", response_model=TemplateOut)
async def update_template(
    template_id: uuid.UUID,
    body:        TemplateUpdate,
    request:     Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, template_id=template_id, org_id=member.org_id)
    changed: dict[str, object] = {}

    try:
        if body.title is not None:
            v = svc_97.validate_title(body.title)
            if v != row.title:
                changed["title"] = v
                row.title = v
        if body.amount is not None:
            v = svc_97.validate_amount(body.amount)
            if v != row.amount:
                changed["amount"] = str(v)
                row.amount = v
        if body.currency is not None:
            v = svc_97.validate_currency(body.currency)
            if v != row.currency:
                changed["currency"] = v
                row.currency = v
        if body.description is not None:
            row.description = svc_97.validate_description(body.description)
            changed["description"] = True
        if body.interval_count is not None:
            row.interval_count = svc_97.validate_interval(body.interval_count)
            changed["interval_count"] = row.interval_count
        if body.cadence is not None:
            cadence_s = svc_97.validate_cadence(body.cadence)
            row.cadence = RecurringExpenseCadence(cadence_s)
            changed["cadence"] = cadence_s
        if body.start_date is not None or body.end_date is not None:
            new_start = body.start_date if body.start_date is not None else row.start_date
            new_end = body.end_date if body.end_date is not None else row.end_date
            s, e = svc_97.validate_dates(start_date=new_start, end_date=new_end)
            row.start_date = s
            row.end_date = e
            changed["dates"] = True
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))

    if body.category_id is not None:
        await _assert_category_belongs(
            db, category_id=body.category_id, org_id=member.org_id,
        )
        row.category_id = body.category_id
        changed["category_id"] = str(body.category_id)
    if body.supplier_id is not None:
        await _assert_supplier_belongs(
            db, supplier_id=body.supplier_id, org_id=member.org_id,
        )
        row.supplier_id = body.supplier_id
        changed["supplier_id"] = str(body.supplier_id)

    # Recompute next_due if cadence / interval / dates changed and
    # nothing has been generated yet.
    if changed and row.last_generated_expense_id is None:
        nd = svc_97.compute_next_due(
            start_date=row.start_date,
            cadence=row.cadence.value,
            interval=row.interval_count,
            last_generated=None,
            end_date=row.end_date,
        )
        if nd is None:
            raise HTTPException(
                status_code=400,
                detail="schedule ends before any occurrence",
            )
        row.next_due_date = nd

    await log_action(
        db,
        action="recurring_expense.updated",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="recurring_expense_template",
        target_id=str(row.id),
        request=request,
        extra={"changed": changed},
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: uuid.UUID,
    request:     Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, template_id=template_id, org_id=member.org_id)
    title = row.title
    await db.delete(row)
    await log_action(
        db,
        action="recurring_expense.deleted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="recurring_expense_template",
        target_id=str(template_id),
        request=request,
        extra={"title": title},
    )
    await db.commit()


@router.post("/{template_id}/generate", response_model=GenerateOut)
async def generate_expense(
    template_id: uuid.UUID,
    request:     Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, template_id=template_id, org_id=member.org_id)
    if not row.is_active:
        raise HTTPException(status_code=400, detail="template is paused")
    if row.end_date is not None and row.next_due_date > row.end_date:
        raise HTTPException(status_code=400, detail="schedule has ended")

    expense = Expense(
        org_id=member.org_id,
        created_by=uuid.UUID(user["user_id"]),
        category_id=row.category_id,
        supplier_id=row.supplier_id,
        amount=row.amount,
        currency=row.currency,
        description=row.description,
        expense_date=row.next_due_date,
        status=ExpenseStatus.DRAFT,
    )
    db.add(expense)
    await db.flush()

    now = datetime.now(timezone.utc)
    row.last_generated_at = now
    row.last_generated_expense_id = expense.id
    row.generated_count = int(row.generated_count or 0) + 1

    # Advance the schedule. If the new next_due passes end_date, the
    # template is finished — auto-deactivate so the scheduler stops
    # picking it up.
    nd = svc_97.compute_next_due(
        start_date=row.start_date,
        cadence=row.cadence.value,
        interval=row.interval_count,
        last_generated=row.next_due_date,
        end_date=row.end_date,
    )
    if nd is None:
        row.is_active = False
    else:
        row.next_due_date = nd

    await log_action(
        db,
        action="recurring_expense.generated",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="recurring_expense_template",
        target_id=str(row.id),
        request=request,
        extra={
            "expense_id": str(expense.id),
            "next_due_date": nd.isoformat() if nd else None,
        },
    )
    await db.commit()

    return GenerateOut(expense_id=expense.id, next_due_date=nd)


@router.post("/{template_id}/pause", response_model=TemplateOut)
async def pause_template(
    template_id: uuid.UUID,
    request:     Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, template_id=template_id, org_id=member.org_id)
    if row.is_active:
        row.is_active = False
        await log_action(
            db,
            action="recurring_expense.paused",
            org_id=member.org_id,
            actor_user_id=user["user_id"],
            target_type="recurring_expense_template",
            target_id=str(row.id),
            request=request,
        )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.post("/{template_id}/resume", response_model=TemplateOut)
async def resume_template(
    template_id: uuid.UUID,
    request:     Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, template_id=template_id, org_id=member.org_id)
    if not row.is_active:
        if row.end_date is not None and row.next_due_date > row.end_date:
            raise HTTPException(
                status_code=400,
                detail="schedule has ended — cannot resume",
            )
        row.is_active = True
        await log_action(
            db,
            action="recurring_expense.resumed",
            org_id=member.org_id,
            actor_user_id=user["user_id"],
            target_type="recurring_expense_template",
            target_id=str(row.id),
            request=request,
        )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.get("/{template_id}/preview", response_model=PreviewOut)
async def preview_template(
    template_id: uuid.UUID,
    count: int = Query(default=12, ge=1, le=60),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    row = await _load(db, template_id=template_id, org_id=member.org_id)
    dates = svc_97.plan_occurrences(
        start_date=row.start_date,
        cadence=row.cadence.value,
        interval=row.interval_count,
        end_date=row.end_date,
        count=count,
    )
    return PreviewOut(dates=dates)
