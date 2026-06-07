"""Budget vs Actual P&L router.

Endpoints:
  GET    /api/accounting/budgets                      list budgets
  POST   /api/accounting/budgets                      create
  GET    /api/accounting/budgets/{id}                 detail with lines
  PUT    /api/accounting/budgets/{id}/lines           bulk upsert lines
  POST   /api/accounting/budgets/{id}/approve         lock budget
  GET    /api/accounting/budgets/{id}/vs-actual       compare vs journal actuals
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.accounting import JournalEntry, JournalLine
from app.models.budget import Budget, BudgetLine
from app.models.organization import OrgRole
from app.services.audit import log_action

router = APIRouter(prefix="/api/accounting/budgets", tags=["budget"], dependencies=[Depends(require_module("finance"))])
log = logging.getLogger(__name__)


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _actor(ctx: tuple) -> uuid.UUID:
    user, _ = ctx
    return user["user_id"]


def _require_owner_or_admin(ctx: tuple) -> None:
    _, member = ctx
    if member.role not in (OrgRole.OWNER, OrgRole.ADMIN):
        raise HTTPException(status_code=403, detail="Owner or admin required")


# ─── Schemas ──────────────────────────────────────────────────────────────

class BudgetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    fiscal_year: int = Field(..., ge=2000, le=2100)
    department: Optional[str] = Field(default=None, max_length=100)


class BudgetLineIn(BaseModel):
    account_code: str = Field(..., min_length=1, max_length=10)
    month: int = Field(..., ge=1, le=12)
    amount: Decimal = Field(..., ge=0)


class BudgetLineOut(BaseModel):
    id: uuid.UUID
    account_code: str
    month: int
    amount: Decimal

    model_config = {"from_attributes": True}


class BudgetOut(BaseModel):
    id: uuid.UUID
    name: str
    fiscal_year: int
    department: Optional[str] = None
    status: str
    submitted_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    approved_at: Optional[datetime]
    created_at: datetime
    lines: list[BudgetLineOut] = []

    model_config = {"from_attributes": True}


class VsActualLine(BaseModel):
    account_code: str
    month: int
    budget: Decimal
    actual: Decimal
    variance: Decimal
    variance_pct: Optional[Decimal]


# ─── Endpoints ────────────────────────────────────────────────────────────

@router.get("", response_model=list[BudgetOut])
async def list_budgets(
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    try:
        org_id = _org(ctx)
        rows = (
            await db.execute(
                select(Budget)
                .where(Budget.org_id == org_id)
                .options(selectinload(Budget.lines))
                .order_by(Budget.fiscal_year.desc())
            )
        ).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_budgets failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=BudgetOut, status_code=201)
async def create_budget(
    body: BudgetCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)
        budget = Budget(
            org_id=org_id,
            name=body.name,
            fiscal_year=body.fiscal_year,
            department=body.department,
            status="DRAFT",
            created_by=_actor(ctx),
        )
        db.add(budget)
        await db.commit()
        await db.refresh(budget)
        await log_action(db, action="budget.created", org_id=org_id,
                         actor_user_id=_actor(ctx), target_type="budget",
                         target_id=budget.id, request=request)
        await db.commit()
        return budget
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_budget failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{budget_id}", response_model=BudgetOut)
async def get_budget(
    budget_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    try:
        org_id = _org(ctx)
        budget = (
            await db.execute(
                select(Budget)
                .where(Budget.id == budget_id, Budget.org_id == org_id)
                .options(selectinload(Budget.lines))
            )
        ).scalar_one_or_none()
        if not budget:
            raise HTTPException(status_code=404, detail="Budget not found")
        return budget
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"get_budget failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{budget_id}/lines", response_model=BudgetOut)
async def upsert_lines(
    budget_id: uuid.UUID,
    body: list[BudgetLineIn],
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """Bulk upsert: replaces the row for each (account_code, month) pair."""
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)
        budget = (
            await db.execute(
                select(Budget)
                .where(Budget.id == budget_id, Budget.org_id == org_id)
                .options(selectinload(Budget.lines))
            )
        ).scalar_one_or_none()
        if not budget:
            raise HTTPException(status_code=404, detail="Budget not found")
        if budget.status != "DRAFT":
            raise HTTPException(status_code=409, detail="Only DRAFT budgets can be edited")

        # Build lookup of existing lines
        existing = {(l.account_code, l.month): l for l in budget.lines}
        for item in body:
            key = (item.account_code, item.month)
            if key in existing:
                existing[key].amount = item.amount
            else:
                line = BudgetLine(
                    budget_id=budget.id,
                    account_code=item.account_code,
                    month=item.month,
                    amount=item.amount,
                )
                db.add(line)

        await db.commit()
        await db.refresh(budget)
        # Reload lines after commit
        budget = (
            await db.execute(
                select(Budget)
                .where(Budget.id == budget_id)
                .options(selectinload(Budget.lines))
            )
        ).scalar_one()
        return budget
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"upsert_lines failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{budget_id}/approve", response_model=BudgetOut)
async def approve_budget(
    budget_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)
        budget = (
            await db.execute(
                select(Budget)
                .where(Budget.id == budget_id, Budget.org_id == org_id)
                .options(selectinload(Budget.lines))
            )
        ).scalar_one_or_none()
        if not budget:
            raise HTTPException(status_code=404, detail="Budget not found")
        if budget.status != "DRAFT":
            raise HTTPException(status_code=409, detail="Only DRAFT budgets can be approved")

        budget.status = "APPROVED"
        budget.approved_by = _actor(ctx)
        budget.approved_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(budget)
        await log_action(db, action="budget.approved", org_id=org_id,
                         actor_user_id=_actor(ctx), target_type="budget",
                         target_id=budget.id, request=request)
        await db.commit()
        return budget
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"approve_budget failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{budget_id}/vs-actual", response_model=list[VsActualLine])
async def vs_actual(
    budget_id: uuid.UUID,
    year: int,
    month: int,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """Compare budget lines to actual journal lines for the given year+month."""
    try:
        org_id = _org(ctx)
        budget = (
            await db.execute(
                select(Budget)
                .where(Budget.id == budget_id, Budget.org_id == org_id)
                .options(selectinload(Budget.lines))
            )
        ).scalar_one_or_none()
        if not budget:
            raise HTTPException(status_code=404, detail="Budget not found")

        from datetime import date
        period_start = date(year, month, 1)
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        period_end = date(year, month, last_day)

        # Aggregate actuals from journal lines for this period
        rows = (
            await db.execute(
                select(
                    JournalLine.account_code,
                    func.sum(JournalLine.debit - JournalLine.credit).label("net"),
                )
                .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
                .where(
                    JournalEntry.org_id == org_id,
                    JournalEntry.entry_date >= period_start,
                    JournalEntry.entry_date <= period_end,
                    JournalEntry.is_posted == True,  # noqa: E712
                )
                .group_by(JournalLine.account_code)
            )
        ).all()

        actuals: dict[str, Decimal] = {r.account_code: Decimal(str(r.net or 0)) for r in rows}

        result: list[VsActualLine] = []
        for line in budget.lines:
            if line.month != month:
                continue
            actual = actuals.get(line.account_code, Decimal("0"))
            variance = actual - line.amount
            variance_pct = (
                (variance / line.amount * 100).quantize(Decimal("0.01"))
                if line.amount != 0
                else None
            )
            result.append(VsActualLine(
                account_code=line.account_code,
                month=line.month,
                budget=line.amount,
                actual=actual,
                variance=variance,
                variance_pct=variance_pct,
            ))

        return result
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"vs_actual failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Department budget workflow ─────────────────────────────────────────────────

class SubmitIn(BaseModel):
    """Optional message from dept manager when submitting for CEO review."""
    note: Optional[str] = None


class RequestChangesIn(BaseModel):
    notes: str = Field(..., min_length=1, max_length=2000)


@router.post("/{budget_id}/submit")
async def submit_budget(
    budget_id: uuid.UUID,
    body: SubmitIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Department manager submits a DRAFT budget for CEO/OWNER review."""
    org_id = _org(ctx)
    actor = _actor(ctx)
    try:
        budget = await db.scalar(
            select(Budget).where(Budget.id == budget_id, Budget.org_id == org_id)
        )
        if not budget:
            raise HTTPException(status_code=404, detail="Budget not found")
        if budget.status not in ("DRAFT", "CHANGES_REQUESTED"):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot submit a budget in status {budget.status}",
            )
        budget.status = "SUBMITTED"
        budget.submitted_by_user_id = actor
        budget.submitted_at = datetime.now(timezone.utc)
        if body.note:
            budget.review_notes = body.note
        await db.commit()
        await db.refresh(budget)
        budget.lines = []
        return BudgetOut.model_validate(budget)
    except HTTPException:
        raise
    except Exception as e:
        log.error("submit_budget failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/submissions")
async def list_submissions(
    fiscal_year: Optional[int] = None,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """CEO / OWNER view — list all SUBMITTED or CHANGES_REQUESTED budgets."""
    _require_owner_or_admin(ctx)
    org_id = _org(ctx)
    try:
        q = (
            select(Budget)
            .where(
                Budget.org_id == org_id,
                Budget.status.in_(["SUBMITTED", "CHANGES_REQUESTED", "APPROVED"]),
            )
            .options(selectinload(Budget.lines))
            .order_by(Budget.submitted_at.desc())
        )
        if fiscal_year:
            q = q.where(Budget.fiscal_year == fiscal_year)
        budgets = (await db.execute(q)).scalars().all()
        return [BudgetOut.model_validate(b) for b in budgets]
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_submissions failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{budget_id}/request-changes")
async def request_budget_changes(
    budget_id: uuid.UUID,
    body: RequestChangesIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """CEO / OWNER sends a SUBMITTED budget back for revisions with notes."""
    _require_owner_or_admin(ctx)
    org_id = _org(ctx)
    try:
        budget = await db.scalar(
            select(Budget).where(Budget.id == budget_id, Budget.org_id == org_id)
        )
        if not budget:
            raise HTTPException(status_code=404, detail="Budget not found")
        if budget.status != "SUBMITTED":
            raise HTTPException(
                status_code=409,
                detail=f"Budget status is {budget.status} — must be SUBMITTED",
            )
        budget.status = "CHANGES_REQUESTED"
        budget.review_notes = body.notes
        await db.commit()
        await db.refresh(budget)
        budget.lines = []
        return BudgetOut.model_validate(budget)
    except HTTPException:
        raise
    except Exception as e:
        log.error("request_budget_changes failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
