"""Financial reports: P&L, Balance Sheet, Cash Flow.

All endpoints are PRO+ only and read from the journal_entries /
journal_lines tables populated by the ledger service.

Endpoints:
  GET /api/accounting/reports/pnl?from=&to=
  GET /api/accounting/reports/balance-sheet?as_of=
  GET /api/accounting/reports/cash-flow?from=&to=
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_plan
from app.models.accounting import AccountType, ChartOfAccount, JournalEntry, JournalLine
from app.models.organization import OrgPlan

router = APIRouter(prefix="/api/accounting/reports", tags=["financial_reports"])
log = logging.getLogger(__name__)


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ─── Schemas ───────────────────────────────────────────────────────────────

class ReportLine(BaseModel):
    code: str
    name: str
    account_type: AccountType
    account_subtype: Optional[str]
    amount: Decimal


class PnLReport(BaseModel):
    from_date: date
    to_date: date
    revenue_lines: list[ReportLine]
    expense_lines: list[ReportLine]
    total_revenue: Decimal
    total_expenses: Decimal
    net_income: Decimal


class BalanceSheetReport(BaseModel):
    as_of: date
    asset_lines: list[ReportLine]
    liability_lines: list[ReportLine]
    equity_lines: list[ReportLine]
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    is_balanced: bool


class CashFlowLine(BaseModel):
    source_type: str
    amount: Decimal
    count: int


class CashFlowReport(BaseModel):
    from_date: date
    to_date: date
    cash_in: list[CashFlowLine]
    cash_out: list[CashFlowLine]
    net_cash_flow: Decimal


# ─── Helper: per-account net balance ───────────────────────────────────────

async def _account_balances(
    db: AsyncSession,
    org_id: uuid.UUID,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    account_types: Optional[list[AccountType]] = None,
) -> dict[str, tuple[Decimal, Decimal]]:
    """Return {account_code: (debit_total, credit_total)} for the given filters."""
    filters = [
        JournalEntry.org_id == org_id,
        JournalEntry.is_posted == True,  # noqa: E712
    ]
    if from_date:
        filters.append(JournalEntry.entry_date >= from_date)
    if to_date:
        filters.append(JournalEntry.entry_date <= to_date)

    rows = (
        await db.execute(
            select(
                JournalLine.account_code,
                func.coalesce(func.sum(JournalLine.debit), 0).label("dt"),
                func.coalesce(func.sum(JournalLine.credit), 0).label("ct"),
            )
            .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
            .where(and_(*filters))
            .group_by(JournalLine.account_code)
        )
    ).all()

    return {row.account_code: (Decimal(str(row.dt)), Decimal(str(row.ct))) for row in rows}


async def _get_accounts(
    db: AsyncSession,
    org_id: uuid.UUID,
    account_types: list[AccountType],
) -> list[ChartOfAccount]:
    rows = (
        await db.execute(
            select(ChartOfAccount)
            .where(
                ChartOfAccount.org_id == org_id,
                ChartOfAccount.account_type.in_(account_types),
                ChartOfAccount.is_active == True,  # noqa
            )
            .order_by(ChartOfAccount.code)
        )
    ).scalars().all()
    return rows


# ─── P&L ───────────────────────────────────────────────────────────────────

@router.get("/pnl", response_model=PnLReport)
async def pnl_report(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
    _plan: None = Depends(require_plan(OrgPlan.PRO)),
):
    """Profit & Loss report for a date range, derived from journal entries."""
    try:
        org_id = _org(ctx)
        balances = await _account_balances(db, org_id, from_date=from_date, to_date=to_date)
        rev_accts = await _get_accounts(db, org_id, [AccountType.REVENUE])
        exp_accts = await _get_accounts(db, org_id, [AccountType.EXPENSE])

        revenue_lines: list[ReportLine] = []
        total_rev = Decimal("0")
        for acct in rev_accts:
            dt, ct = balances.get(acct.code, (Decimal("0"), Decimal("0")))
            # Revenue: credit balance (credit > debit = positive revenue)
            amount = ct - dt
            if amount != 0:
                revenue_lines.append(ReportLine(
                    code=acct.code, name=acct.name,
                    account_type=acct.account_type,
                    account_subtype=acct.account_subtype,
                    amount=amount,
                ))
                total_rev += amount

        expense_lines: list[ReportLine] = []
        total_exp = Decimal("0")
        for acct in exp_accts:
            dt, ct = balances.get(acct.code, (Decimal("0"), Decimal("0")))
            # Expense: debit balance
            amount = dt - ct
            if amount != 0:
                expense_lines.append(ReportLine(
                    code=acct.code, name=acct.name,
                    account_type=acct.account_type,
                    account_subtype=acct.account_subtype,
                    amount=amount,
                ))
                total_exp += amount

        return PnLReport(
            from_date=from_date,
            to_date=to_date,
            revenue_lines=revenue_lines,
            expense_lines=expense_lines,
            total_revenue=total_rev,
            total_expenses=total_exp,
            net_income=total_rev - total_exp,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"pnl_report failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ─── Balance Sheet ──────────────────────────────────────────────────────────

@router.get("/balance-sheet", response_model=BalanceSheetReport)
async def balance_sheet(
    as_of: date = Query(default_factory=date.today),
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
    _plan: None = Depends(require_plan(OrgPlan.PRO)),
):
    """Balance sheet snapshot as of a date (cumulative from all journal entries)."""
    try:
        org_id = _org(ctx)
        # Cumulative balances from the beginning of time up to as_of
        balances = await _account_balances(db, org_id, to_date=as_of)

        asset_accts = await _get_accounts(db, org_id, [AccountType.ASSET])
        liab_accts  = await _get_accounts(db, org_id, [AccountType.LIABILITY])
        eq_accts    = await _get_accounts(db, org_id, [AccountType.EQUITY])

        def make_lines(accts, debit_normal: bool) -> tuple[list[ReportLine], Decimal]:
            lines = []
            total = Decimal("0")
            for acct in accts:
                dt, ct = balances.get(acct.code, (Decimal("0"), Decimal("0")))
                amount = (dt - ct) if debit_normal else (ct - dt)
                lines.append(ReportLine(
                    code=acct.code, name=acct.name,
                    account_type=acct.account_type,
                    account_subtype=acct.account_subtype,
                    amount=amount,
                ))
                total += amount
            return lines, total

        asset_lines, total_assets = make_lines(asset_accts, debit_normal=True)
        liab_lines,  total_liabs  = make_lines(liab_accts,  debit_normal=False)
        eq_lines,    total_equity = make_lines(eq_accts,    debit_normal=False)

        return BalanceSheetReport(
            as_of=as_of,
            asset_lines=asset_lines,
            liability_lines=liab_lines,
            equity_lines=eq_lines,
            total_assets=total_assets,
            total_liabilities=total_liabs,
            total_equity=total_equity,
            is_balanced=abs(total_assets - (total_liabs + total_equity)) < Decimal("0.01"),
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"balance_sheet failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ─── Cash Flow ──────────────────────────────────────────────────────────────

@router.get("/cash-flow", response_model=CashFlowReport)
async def cash_flow(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
    _plan: None = Depends(require_plan(OrgPlan.PRO)),
):
    """Cash flow: net movements in account 1920 (bank/cash) grouped by source_type."""
    try:
        org_id = _org(ctx)
        CASH_ACCOUNT = "1920"

        rows = (
            await db.execute(
                select(
                    JournalEntry.source_type,
                    func.coalesce(func.sum(JournalLine.debit), 0).label("dt"),
                    func.coalesce(func.sum(JournalLine.credit), 0).label("ct"),
                    func.count(JournalEntry.id.distinct()).label("cnt"),
                )
                .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
                .where(
                    JournalEntry.org_id == org_id,
                    JournalEntry.is_posted == True,  # noqa
                    JournalEntry.entry_date >= from_date,
                    JournalEntry.entry_date <= to_date,
                    JournalLine.account_code == CASH_ACCOUNT,
                )
                .group_by(JournalEntry.source_type)
            )
        ).all()

        cash_in: list[CashFlowLine] = []
        cash_out: list[CashFlowLine] = []
        net = Decimal("0")

        for row in rows:
            dt = Decimal(str(row.dt))
            ct = Decimal(str(row.ct))
            source = row.source_type or "MANUAL"
            net_flow = dt - ct
            net += net_flow
            entry = CashFlowLine(source_type=source, amount=abs(net_flow), count=row.cnt)
            if net_flow >= 0:
                cash_in.append(entry)
            else:
                cash_out.append(entry)

        return CashFlowReport(
            from_date=from_date,
            to_date=to_date,
            cash_in=cash_in,
            cash_out=cash_out,
            net_cash_flow=net,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"cash_flow failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
