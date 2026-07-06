"""Cash Flow Forecast — forward-looking 30/60/90-day projection.

GET  /api/reports/cashflow          — JSON forecast
POST /api/reports/cashflow/adjustments  — create manual adjustment
DELETE /api/reports/cashflow/adjustments/{adj_id} — remove adjustment
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module

log = logging.getLogger(__name__)
router = APIRouter(tags=["cashflow"], dependencies=[Depends(require_module("finance"))])

ZERO = Decimal("0")


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class CashFlowItem(BaseModel):
    id: str
    source: str  # invoice | recurring | expense | purchase_order | payroll | adjustment
    label: str
    best_date: date
    worst_date: date
    amount: Decimal  # positive = inflow, negative = outflow


class DayPoint(BaseModel):
    date: date
    inflows: Decimal
    outflows: Decimal
    net: Decimal
    balance: Decimal  # cumulative from day 1 of horizon


class AdjustmentOut(BaseModel):
    id: uuid.UUID
    adjustment_date: date
    label: str
    amount: Decimal
    note: Optional[str]
    created_at: datetime


class CashFlowResponse(BaseModel):
    horizon_days: int
    best_case: list[DayPoint]
    worst_case: list[DayPoint]
    items: list[CashFlowItem]
    adjustments: list[AdjustmentOut]
    best_negative_dates: list[str]
    worst_negative_dates: list[str]


class AdjustmentCreate(BaseModel):
    adjustment_date: date
    label: str = Field(..., min_length=1, max_length=200)
    amount: Decimal  # positive = expected inflow, negative = expected outflow
    note: Optional[str] = None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _build_daily_series(
    items: list[CashFlowItem],
    today: date,
    end_date: date,
    scenario: str,  # "best" | "worst"
) -> tuple[list[DayPoint], list[str]]:
    """Build a cumulative daily cash position. Returns (series, negative_date_strs)."""
    bucket: dict[date, dict[str, Decimal]] = {}
    d = today
    while d <= end_date:
        bucket[d] = {"inflows": ZERO, "outflows": ZERO}
        d += timedelta(days=1)

    for item in items:
        dt = item.best_date if scenario == "best" else item.worst_date
        if dt < today:
            dt = today
        if dt > end_date:
            continue
        if item.amount >= ZERO:
            bucket[dt]["inflows"] += item.amount
        else:
            bucket[dt]["outflows"] += abs(item.amount)

    points: list[DayPoint] = []
    negative: list[str] = []
    balance = ZERO
    for d in sorted(bucket.keys()):
        net = bucket[d]["inflows"] - bucket[d]["outflows"]
        balance += net
        points.append(DayPoint(
            date=d,
            inflows=bucket[d]["inflows"].quantize(Decimal("0.01")),
            outflows=bucket[d]["outflows"].quantize(Decimal("0.01")),
            net=net.quantize(Decimal("0.01")),
            balance=balance.quantize(Decimal("0.01")),
        ))
        if balance < ZERO:
            negative.append(d.isoformat())

    return points, negative


# ─── Data collectors ──────────────────────────────────────────────────────────

async def _invoice_items(
    db: AsyncSession, org_id: uuid.UUID, today: date, end_date: date
) -> list[CashFlowItem]:
    from app.features.invoicing.models import Invoice, Customer
    rows = (await db.execute(
        select(Invoice.id, Invoice.invoice_number, Invoice.due_date, Invoice.total_sek,
               Customer.company_name.label("customer_name"))
        .join(Customer, Invoice.customer_id == Customer.id, isouter=True)
        .where(
            Invoice.org_id == org_id,
            Invoice.status.in_(["SENT", "OVERDUE"]),
            Invoice.due_date.isnot(None),
            # worst-case upper bound: due_date + 30 ≤ end_date
            Invoice.due_date <= end_date + timedelta(days=30),
        )
    )).all()

    items: list[CashFlowItem] = []
    for r in rows:
        due = r.due_date
        best_d = max(today, due)
        worst_d = max(today, due + timedelta(days=30))
        items.append(CashFlowItem(
            id=str(r.id),
            source="invoice",
            label=f"{r.customer_name or 'Customer'} — {r.invoice_number}",
            best_date=best_d,
            worst_date=worst_d,
            amount=Decimal(str(r.total_sek)).quantize(Decimal("0.01")),
        ))
    return items


async def _recurring_items(
    db: AsyncSession, org_id: uuid.UUID, today: date, end_date: date
) -> list[CashFlowItem]:
    from app.features.invoicing.models import RecurringInvoice, Invoice as Inv
    rows = (await db.execute(
        select(
            RecurringInvoice.id,
            RecurringInvoice.next_run_date,
            RecurringInvoice.frequency,
            Inv.total_sek,
            Inv.invoice_number,
        )
        .join(Inv, RecurringInvoice.template_invoice_id == Inv.id, isouter=True)
        .where(
            RecurringInvoice.org_id == org_id,
            RecurringInvoice.is_active.is_(True),
            RecurringInvoice.next_run_date.isnot(None),
            RecurringInvoice.next_run_date <= end_date,
        )
    )).all()

    items: list[CashFlowItem] = []
    for r in rows:
        if not r.total_sek:
            continue
        amount = Decimal(str(r.total_sek)).quantize(Decimal("0.01"))
        freq = (r.frequency.value if hasattr(r.frequency, "value") else str(r.frequency)).upper()
        delta = timedelta(days=7) if freq == "WEEKLY" else None

        run_date = r.next_run_date
        occurrence = 0
        while run_date <= end_date:
            occurrence += 1
            d = max(today, run_date)
            items.append(CashFlowItem(
                id=f"{r.id}-{occurrence}",
                source="recurring",
                label=f"Recurring {r.invoice_number or 'invoice'} (run {occurrence})",
                best_date=d,
                worst_date=d,
                amount=amount,
            ))
            if delta:
                run_date += delta
            else:
                # Monthly: advance by one month
                m = run_date.month + 1
                y = run_date.year
                if m > 12:
                    m = 1
                    y += 1
                from calendar import monthrange
                last = monthrange(y, m)[1]
                run_date = date(y, m, min(run_date.day, last))
    return items


async def _expense_items(
    db: AsyncSession, org_id: uuid.UUID, today: date, end_date: date
) -> list[CashFlowItem]:
    from app.features.expenses.models import Expense, ExpenseStatus
    rows = (await db.execute(
        select(Expense.id, Expense.description, Expense.expense_date, Expense.amount)
        .where(
            Expense.org_id == org_id,
            Expense.status == ExpenseStatus.APPROVED,
            Expense.expense_date >= today,
            Expense.expense_date <= end_date,
        )
    )).all()

    return [
        CashFlowItem(
            id=str(r.id),
            source="expense",
            label=r.description or "Approved expense",
            best_date=r.expense_date,
            worst_date=r.expense_date,
            amount=-Decimal(str(r.amount)).quantize(Decimal("0.01")),
        )
        for r in rows
    ]


async def _po_items(
    db: AsyncSession, org_id: uuid.UUID, today: date, end_date: date
) -> list[CashFlowItem]:
    from app.features.inventory.models import PurchaseOrder, PurchaseOrderStatus
    rows = (await db.execute(
        select(PurchaseOrder.id, PurchaseOrder.created_at, PurchaseOrder.total)
        .where(
            PurchaseOrder.org_id == org_id,
            PurchaseOrder.status == PurchaseOrderStatus.SENT,
        )
    )).all()

    items: list[CashFlowItem] = []
    for r in rows:
        created = r.created_at.date() if isinstance(r.created_at, datetime) else r.created_at
        expected = created + timedelta(days=45)
        if expected < today or expected > end_date:
            continue
        items.append(CashFlowItem(
            id=str(r.id),
            source="purchase_order",
            label=f"Purchase Order (PO payment due ~{expected.isoformat()})",
            best_date=expected,
            worst_date=expected,
            amount=-Decimal(str(r.total)).quantize(Decimal("0.01")),
        ))
    return items


async def _payroll_items(
    db: AsyncSession, org_id: uuid.UUID, today: date, end_date: date
) -> list[CashFlowItem]:
    from app.features.hr.payroll_models import PayrollRun
    rows = (await db.execute(
        select(PayrollRun.id, PayrollRun.period_end, PayrollRun.total_employer_cost)
        .where(
            PayrollRun.org_id == org_id,
            PayrollRun.status == "APPROVED",
        )
    )).all()

    items: list[CashFlowItem] = []
    for r in rows:
        pay_date = r.period_end + timedelta(days=5)
        if pay_date < today or pay_date > end_date:
            continue
        items.append(CashFlowItem(
            id=str(r.id),
            source="payroll",
            label=f"Payroll ({r.period_end.isoformat()})",
            best_date=pay_date,
            worst_date=pay_date,
            amount=-Decimal(str(r.total_employer_cost)).quantize(Decimal("0.01")),
        ))
    return items


async def _adjustment_items(
    db: AsyncSession, org_id: uuid.UUID, today: date, end_date: date
) -> tuple[list[CashFlowItem], list[AdjustmentOut]]:
    from .cashflow_models import CashFlowAdjustment
    rows = (await db.execute(
        select(CashFlowAdjustment)
        .where(
            CashFlowAdjustment.org_id == org_id,
            CashFlowAdjustment.adjustment_date >= today,
            CashFlowAdjustment.adjustment_date <= end_date,
        )
        .order_by(CashFlowAdjustment.adjustment_date)
    )).scalars().all()

    items = [
        CashFlowItem(
            id=str(r.id),
            source="adjustment",
            label=r.label,
            best_date=r.adjustment_date,
            worst_date=r.adjustment_date,
            amount=Decimal(str(r.amount)).quantize(Decimal("0.01")),
        )
        for r in rows
    ]
    adj_out = [
        AdjustmentOut(
            id=r.id,
            adjustment_date=r.adjustment_date,
            label=r.label,
            amount=Decimal(str(r.amount)).quantize(Decimal("0.01")),
            note=r.note,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return items, adj_out


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/api/reports/cashflow", response_model=CashFlowResponse)
async def get_cashflow(
    horizon: int = Query(90, ge=7, le=180),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org(ctx)
        today = date.today()
        end_date = today + timedelta(days=horizon)

        inv_items = await _invoice_items(db, org_id, today, end_date)
        rec_items = await _recurring_items(db, org_id, today, end_date)
        exp_items = await _expense_items(db, org_id, today, end_date)
        po_items = await _po_items(db, org_id, today, end_date)
        pay_items = await _payroll_items(db, org_id, today, end_date)
        adj_items, adj_out = await _adjustment_items(db, org_id, today, end_date)

        all_items = inv_items + rec_items + exp_items + po_items + pay_items + adj_items

        best_series, best_neg = _build_daily_series(all_items, today, end_date, "best")
        worst_series, worst_neg = _build_daily_series(all_items, today, end_date, "worst")

        return CashFlowResponse(
            horizon_days=horizon,
            best_case=best_series,
            worst_case=worst_series,
            items=all_items,
            adjustments=adj_out,
            best_negative_dates=best_neg,
            worst_negative_dates=worst_neg,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_cashflow failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/reports/cashflow/adjustments", status_code=201)
async def create_adjustment(
    body: AdjustmentCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        from .cashflow_models import CashFlowAdjustment
        org_id = _org(ctx)
        adj = CashFlowAdjustment(
            org_id=org_id,
            adjustment_date=body.adjustment_date,
            label=body.label,
            amount=body.amount,
            note=body.note,
        )
        db.add(adj)
        await db.commit()
        await db.refresh(adj)
        return AdjustmentOut(
            id=adj.id,
            adjustment_date=adj.adjustment_date,
            label=adj.label,
            amount=Decimal(str(adj.amount)).quantize(Decimal("0.01")),
            note=adj.note,
            created_at=adj.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_adjustment failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/reports/cashflow/adjustments/{adj_id}", status_code=204)
async def delete_adjustment(
    adj_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        from .cashflow_models import CashFlowAdjustment
        org_id = _org(ctx)
        obj = await db.scalar(
            select(CashFlowAdjustment).where(
                CashFlowAdjustment.id == adj_id,
                CashFlowAdjustment.org_id == org_id,
            )
        )
        if not obj:
            raise HTTPException(404, "Adjustment not found")
        await db.delete(obj)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_adjustment failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
