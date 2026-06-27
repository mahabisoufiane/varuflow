"""Expense budgets router (Item 99).

Endpoints under ``/api/expense-budgets``:

    GET    ""                       list budgets (optional period filter)
    POST   ""                       create
    GET    /{budget_id}              detail — includes live spend assessment
    PATCH  /{budget_id}              edit (cap / threshold / note only)
    DELETE /{budget_id}              delete
    GET    /{budget_id}/status       standalone live assessment
    GET    /summary?on=YYYY-MM-DD    every currently-active budget with its
                                    live spend assessment (for dashboards)

Spend totals are computed at read time: we sum ``expenses.amount`` over
(org_id, category_id, expense_date BETWEEN window_start AND window_end)
filtered to non-rejected statuses. No denormalisation — the running
total can't drift.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date as _date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from .expense_budget import ExpenseBudget, ExpenseBudgetPeriod
from .models import Expense, ExpenseCategory, ExpenseStatus
from app.services import expense_budget as svc_99
from app.services.audit import log_action

router = APIRouter(prefix="/api/expense-budgets", tags=["expense-budgets"], dependencies=[Depends(require_module("finance"))])

log = logging.getLogger(__name__)


# ── request / response ─────────────────────────────────────────────────


class BudgetCreate(BaseModel):
    category_id:         uuid.UUID
    period:              str
    period_start:        _date
    amount_cap:          str
    currency:            str = "SEK"
    alert_threshold_pct: int = 80
    note:                str | None = None


class BudgetUpdate(BaseModel):
    amount_cap:          str | None = None
    alert_threshold_pct: int | None = None
    note:                str | None = None


class BudgetOut(BaseModel):
    id:                  uuid.UUID
    category_id:         uuid.UUID
    period:              str
    period_start:        _date
    period_end:          _date
    amount_cap:          str
    currency:            str
    alert_threshold_pct: int
    note:                str | None
    created_at:          datetime
    updated_at:          datetime


class StatusOut(BaseModel):
    budget_id:           uuid.UUID
    category_id:         uuid.UUID
    period:              str
    period_start:        _date
    period_end:          _date
    amount_cap:          str
    spent:               str
    remaining:           str
    pct_used:            int
    level:               str
    over_by:             str
    currency:            str


# ── helpers ────────────────────────────────────────────────────────────


def _to_out(row: ExpenseBudget) -> BudgetOut:
    pe = svc_99.period_end(
        period=row.period.value
        if isinstance(row.period, ExpenseBudgetPeriod) else str(row.period),
        period_start=row.period_start,
    )
    return BudgetOut(
        id=row.id,
        category_id=row.category_id,
        period=row.period.value
        if isinstance(row.period, ExpenseBudgetPeriod) else str(row.period),
        period_start=row.period_start,
        period_end=pe,
        amount_cap=str(row.amount_cap),
        currency=row.currency,
        alert_threshold_pct=row.alert_threshold_pct,
        note=row.note,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _load(
    db: AsyncSession, *, budget_id: uuid.UUID, org_id: uuid.UUID,
) -> ExpenseBudget:
    row = await db.get(ExpenseBudget, budget_id)
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Budget not found")
    return row


async def _assert_category_belongs(
    db: AsyncSession, *, category_id: uuid.UUID, org_id: uuid.UUID,
) -> None:
    found = await db.scalar(
        select(ExpenseCategory.id).where(
            ExpenseCategory.id == category_id,
            ExpenseCategory.org_id == org_id,
        )
    )
    if found is None:
        raise HTTPException(status_code=404, detail="Category not found")


async def _spend_for(
    db: AsyncSession, *,
    org_id: uuid.UUID,
    category_id: uuid.UUID,
    window_start: _date,
    window_end: _date,
) -> Decimal:
    """Sum expense.amount over the window. REJECTED expenses are
    excluded — draft + approved both count toward the budget so the
    UI can warn *before* approval pushes you over.
    """
    total = await db.scalar(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.org_id == org_id,
            Expense.category_id == category_id,
            Expense.expense_date >= window_start,
            Expense.expense_date <= window_end,
            Expense.status != ExpenseStatus.REJECTED,
        )
    )
    return Decimal(str(total or 0))


def _status_out_from(
    row: ExpenseBudget, *, spent: Decimal,
) -> StatusOut:
    period_s = row.period.value if isinstance(row.period, ExpenseBudgetPeriod) else str(row.period)
    pe = svc_99.period_end(period=period_s, period_start=row.period_start)
    a = svc_99.assess(
        cap=Decimal(str(row.amount_cap)),
        spent=spent,
        threshold_pct=row.alert_threshold_pct,
    )
    return StatusOut(
        budget_id=row.id,
        category_id=row.category_id,
        period=period_s,
        period_start=row.period_start,
        period_end=pe,
        amount_cap=str(row.amount_cap),
        spent=str(a.spent),
        remaining=str(a.remaining),
        pct_used=a.pct_used,
        level=a.level,
        over_by=str(a.over_by),
        currency=row.currency,
    )


# ── endpoints ──────────────────────────────────────────────────────────


@router.get("", response_model=list[BudgetOut])
async def list_budgets(
    period: str | None = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    stmt = select(ExpenseBudget).where(ExpenseBudget.org_id == member.org_id)
    if period is not None:
        try:
            p = svc_99.validate_period(period)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        stmt = stmt.where(ExpenseBudget.period == ExpenseBudgetPeriod(p))
    stmt = stmt.order_by(
        ExpenseBudget.period_start.desc(),
        ExpenseBudget.created_at.desc(),
    )
    rows = (await db.scalars(stmt)).all()
    return [_to_out(r) for r in rows]


@router.get("/summary", response_model=list[StatusOut])
async def summary(
    on: _date | None = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    today = on or _date.today()
    rows = (await db.scalars(
        select(ExpenseBudget).where(
            ExpenseBudget.org_id == member.org_id,
        )
    )).all()
    out: list[StatusOut] = []
    for r in rows:
        p = r.period.value if isinstance(r.period, ExpenseBudgetPeriod) else str(r.period)
        if not svc_99.contains(period=p, period_start=r.period_start, day=today):
            continue
        window_end = svc_99.period_end(period=p, period_start=r.period_start)
        spent = await _spend_for(
            db,
            org_id=member.org_id,
            category_id=r.category_id,
            window_start=r.period_start,
            window_end=window_end,
        )
        out.append(_status_out_from(r, spent=spent))
    return out


@router.post("", response_model=BudgetOut, status_code=status.HTTP_201_CREATED)
async def create_budget(
    body:    BudgetCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    try:
        period    = svc_99.validate_period(body.period)
        cap       = svc_99.validate_cap(body.amount_cap)
        threshold = svc_99.validate_threshold_pct(body.alert_threshold_pct)
        currency  = svc_99.validate_currency(body.currency)
        note      = svc_99.validate_note(body.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await _assert_category_belongs(
        db, category_id=body.category_id, org_id=member.org_id,
    )

    # Always snap the caller's anchor to the canonical window start —
    # otherwise the unique index would happily accept "April 15" and
    # "April 20" as separate monthly budgets.
    period_start = svc_99.normalize_period_start(
        period=period, anchor=body.period_start,
    )

    row = ExpenseBudget(
        org_id=member.org_id,
        category_id=body.category_id,
        period=ExpenseBudgetPeriod(period),
        period_start=period_start,
        amount_cap=cap,
        currency=currency,
        alert_threshold_pct=threshold,
        note=note,
        created_by_user_id=uuid.UUID(user["user_id"]),
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="budget already exists for this category + period",
        )

    await log_action(
        db,
        action="expense_budget.created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="expense_budget",
        target_id=str(row.id),
        request=request,
        extra={
            "category_id": str(body.category_id),
            "period": period,
            "period_start": period_start.isoformat(),
            "amount_cap": str(cap),
        },
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.get("/{budget_id}", response_model=BudgetOut)
async def get_budget(
    budget_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    row = await _load(db, budget_id=budget_id, org_id=member.org_id)
    return _to_out(row)


@router.get("/{budget_id}/status", response_model=StatusOut)
async def get_status(
    budget_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    row = await _load(db, budget_id=budget_id, org_id=member.org_id)
    p = row.period.value if isinstance(row.period, ExpenseBudgetPeriod) else str(row.period)
    window_end = svc_99.period_end(period=p, period_start=row.period_start)
    spent = await _spend_for(
        db,
        org_id=member.org_id,
        category_id=row.category_id,
        window_start=row.period_start,
        window_end=window_end,
    )
    return _status_out_from(row, spent=spent)


@router.patch("/{budget_id}", response_model=BudgetOut)
async def update_budget(
    budget_id: uuid.UUID,
    body:      BudgetUpdate,
    request:   Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, budget_id=budget_id, org_id=member.org_id)
    changed: dict[str, object] = {}

    try:
        if body.amount_cap is not None:
            v = svc_99.validate_cap(body.amount_cap)
            if v != row.amount_cap:
                row.amount_cap = v
                changed["amount_cap"] = str(v)
        if body.alert_threshold_pct is not None:
            v = svc_99.validate_threshold_pct(body.alert_threshold_pct)
            if v != row.alert_threshold_pct:
                row.alert_threshold_pct = v
                changed["alert_threshold_pct"] = v
        if body.note is not None:
            row.note = svc_99.validate_note(body.note)
            changed["note"] = True
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await log_action(
        db,
        action="expense_budget.updated",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="expense_budget",
        target_id=str(row.id),
        request=request,
        extra={"changed": changed},
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(
    budget_id: uuid.UUID,
    request:   Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, budget_id=budget_id, org_id=member.org_id)
    category_id = str(row.category_id)
    await db.delete(row)
    await log_action(
        db,
        action="expense_budget.deleted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="expense_budget",
        target_id=str(budget_id),
        request=request,
        extra={"category_id": category_id},
    )
    await db.commit()
