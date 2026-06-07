"""Double-entry ledger router.

Endpoints (all under /api/accounting — same prefix as the SIE4 router,
non-overlapping paths):

  GET    /api/accounting/accounts               list chart of accounts
  POST   /api/accounting/accounts               add a custom account
  PATCH  /api/accounting/accounts/{code}        rename / deactivate
  GET    /api/accounting/journal                paginated journal entries + lines
  POST   /api/accounting/journal                create a manual balanced entry
  GET    /api/accounting/trial-balance          per-account debit/credit totals
  POST   /api/accounting/backfill               seed ledger from existing data (idempotent)

All endpoints require authentication. Write operations require OWNER or ADMIN.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.accounting import AccountType, ChartOfAccount, JournalEntry, JournalLine
from app.models.expenses import Expense, ExpenseStatus
from app.models.invoicing import Invoice, InvoiceStatus, Payment
from app.models.organization import OrgRole
from app.services.audit import log_action
from app.services import ledger as ledger_svc

router = APIRouter(prefix="/api/accounting", tags=["ledger"], dependencies=[Depends(require_module("finance"))])
log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────
# BAS 2024 system accounts seeded per org
# ──────────────────────────────────────────────────────────────────

_SYSTEM_ACCOUNTS: list[dict] = [
    {"code": "1510", "name": "Kundfordringar",         "account_type": AccountType.ASSET,     "account_subtype": "current_asset",       "is_system": True},
    {"code": "1710", "name": "Anläggningstillgångar",  "account_type": AccountType.ASSET,     "account_subtype": "fixed_asset",          "is_system": True},
    {"code": "1920", "name": "Kassa och bank",          "account_type": AccountType.ASSET,     "account_subtype": "cash",                 "is_system": True},
    {"code": "2440", "name": "Leverantörsskulder",      "account_type": AccountType.LIABILITY, "account_subtype": "current_liability",    "is_system": True},
    {"code": "2610", "name": "Utgående moms 25%",       "account_type": AccountType.LIABILITY, "account_subtype": "vat_payable",          "is_system": True},
    {"code": "2621", "name": "Utgående moms 12%",       "account_type": AccountType.LIABILITY, "account_subtype": "vat_payable",          "is_system": True},
    {"code": "2631", "name": "Utgående moms 6%",        "account_type": AccountType.LIABILITY, "account_subtype": "vat_payable",          "is_system": True},
    {"code": "2640", "name": "Ingående moms",           "account_type": AccountType.ASSET,     "account_subtype": "vat_receivable",       "is_system": True},
    {"code": "3000", "name": "Försäljning",             "account_type": AccountType.REVENUE,   "account_subtype": "operating_revenue",    "is_system": True},
    {"code": "4000", "name": "Inköp av varor",          "account_type": AccountType.EXPENSE,   "account_subtype": "cost_of_goods",        "is_system": True},
    {"code": "7210", "name": "Löner",                   "account_type": AccountType.EXPENSE,   "account_subtype": "payroll",              "is_system": True},
    {"code": "7510", "name": "Arbetsgivaravgifter",     "account_type": AccountType.EXPENSE,   "account_subtype": "payroll",              "is_system": True},
    {"code": "7830", "name": "Avskrivningar",           "account_type": AccountType.EXPENSE,   "account_subtype": "depreciation",         "is_system": True},
]


async def _ensure_system_accounts(db: AsyncSession, org_id: uuid.UUID) -> None:
    """Seed BAS 2024 system accounts for the org if not already present."""
    existing = (
        await db.execute(
            select(ChartOfAccount.code).where(
                ChartOfAccount.org_id == org_id,
                ChartOfAccount.is_system == True,  # noqa: E712
            )
        )
    ).scalars().all()
    existing_codes = set(existing)

    for acct in _SYSTEM_ACCOUNTS:
        if acct["code"] not in existing_codes:
            db.add(ChartOfAccount(org_id=org_id, **acct))


# ──────────────────────────────────────────────────────────────────
# Ctx helpers
# ──────────────────────────────────────────────────────────────────

def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _member(ctx: tuple):
    _, member = ctx
    return member


def _actor(ctx: tuple) -> uuid.UUID:
    user, _ = ctx
    return user["user_id"]


def _require_owner_or_admin(ctx: tuple) -> None:
    _, member = ctx
    if member.role not in (OrgRole.OWNER, OrgRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner or admin required")


# ──────────────────────────────────────────────────────────────────
# Pydantic schemas
# ──────────────────────────────────────────────────────────────────

class AccountOut(BaseModel):
    code: str
    name: str
    account_type: AccountType
    account_subtype: Optional[str]
    is_system: bool
    is_active: bool

    model_config = {"from_attributes": True}


class AccountCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=10)
    name: str = Field(..., min_length=1, max_length=120)
    account_type: AccountType
    account_subtype: Optional[str] = None


class AccountPatch(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    is_active: Optional[bool] = None


class JournalLineIn(BaseModel):
    account_code: str = Field(..., min_length=1, max_length=10)
    debit: Decimal = Field(default=Decimal("0"), ge=0)
    credit: Decimal = Field(default=Decimal("0"), ge=0)
    memo: Optional[str] = Field(None, max_length=255)
    currency: str = Field(default="SEK", max_length=3)


class JournalLineOut(BaseModel):
    id: uuid.UUID
    account_code: str
    debit: Decimal
    credit: Decimal
    memo: Optional[str]
    currency: str

    model_config = {"from_attributes": True}


class JournalEntryCreate(BaseModel):
    entry_date: date
    description: str = Field(..., min_length=1, max_length=500)
    reference: Optional[str] = Field(None, max_length=120)
    lines: list[JournalLineIn] = Field(..., min_length=2)

    @model_validator(mode="after")
    def balanced(self) -> "JournalEntryCreate":
        total_debit = sum(l.debit for l in self.lines)
        total_credit = sum(l.credit for l in self.lines)
        if abs(total_debit - total_credit) > Decimal("0.01"):
            raise ValueError(f"Journal entry must balance: debit={total_debit} credit={total_credit}")
        return self


class JournalEntryOut(BaseModel):
    id: uuid.UUID
    entry_date: date
    description: str
    source_type: Optional[str]
    reference: Optional[str]
    is_posted: bool
    created_at: datetime
    lines: list[JournalLineOut]

    model_config = {"from_attributes": True}


class TrialBalanceLine(BaseModel):
    code: str
    name: str
    account_type: AccountType
    debit_total: Decimal
    credit_total: Decimal
    balance: Decimal  # positive = debit balance, negative = credit balance


class TrialBalanceOut(BaseModel):
    as_of: date
    lines: list[TrialBalanceLine]
    total_debits: Decimal
    total_credits: Decimal
    is_balanced: bool


class BackfillResult(BaseModel):
    invoices_posted: int
    payments_posted: int
    expenses_posted: int
    skipped: int


# ──────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────

@router.get("/accounts", response_model=list[AccountOut])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """Return the full chart of accounts for this org (seeds system accounts on first call)."""
    try:
        org_id = _org(ctx)
        await _ensure_system_accounts(db, org_id)
        await db.commit()
        rows = (
            await db.execute(
                select(ChartOfAccount)
                .where(ChartOfAccount.org_id == org_id)
                .order_by(ChartOfAccount.code)
            )
        ).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_accounts failed: {e}", extra={"org_id": str(_org(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/accounts", response_model=AccountOut, status_code=201)
async def create_account(
    body: AccountCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """Add a custom account to the chart of accounts."""
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)

        existing = (
            await db.execute(
                select(ChartOfAccount).where(
                    ChartOfAccount.org_id == org_id,
                    ChartOfAccount.code == body.code,
                )
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail=f"Account {body.code} already exists")

        acct = ChartOfAccount(
            org_id=org_id,
            code=body.code,
            name=body.name,
            account_type=body.account_type,
            account_subtype=body.account_subtype,
            is_system=False,
        )
        db.add(acct)
        await db.commit()
        await db.refresh(acct)
        await log_action(db, action="ledger.account_created", org_id=org_id,
                         actor_user_id=_actor(ctx), target_type="account",
                         target_id=acct.id, request=request, extra={"code": body.code})
        await db.commit()
        return acct
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_account failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/accounts/{code}", response_model=AccountOut)
async def patch_account(
    code: str,
    body: AccountPatch,
    request: Request,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """Rename or deactivate an account. System accounts cannot be deleted but can be deactivated."""
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)
        acct = (
            await db.execute(
                select(ChartOfAccount).where(
                    ChartOfAccount.org_id == org_id,
                    ChartOfAccount.code == code,
                )
            )
        ).scalar_one_or_none()
        if not acct:
            raise HTTPException(status_code=404, detail="Account not found")

        if body.name is not None:
            acct.name = body.name
        if body.is_active is not None:
            acct.is_active = body.is_active

        await db.commit()
        await db.refresh(acct)
        return acct
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"patch_account failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/journal", response_model=dict)
async def list_journal(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    source_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """Return paginated journal entries with their lines."""
    try:
        org_id = _org(ctx)
        filters = [JournalEntry.org_id == org_id]
        if from_date:
            filters.append(JournalEntry.entry_date >= from_date)
        if to_date:
            filters.append(JournalEntry.entry_date <= to_date)
        if source_type:
            filters.append(JournalEntry.source_type == source_type.upper())

        total = (
            await db.execute(
                select(func.count(JournalEntry.id)).where(and_(*filters))
            )
        ).scalar_one()

        rows = (
            await db.execute(
                select(JournalEntry)
                .where(and_(*filters))
                .options(selectinload(JournalEntry.lines))
                .order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
                .limit(per_page)
                .offset((page - 1) * per_page)
            )
        ).scalars().all()

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "items": [JournalEntryOut.model_validate(r) for r in rows],
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_journal failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/journal", response_model=JournalEntryOut, status_code=201)
async def create_manual_entry(
    body: JournalEntryCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """Create a manual balanced journal entry."""
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)
        actor_id = _actor(ctx)

        entry = JournalEntry(
            org_id=org_id,
            entry_date=body.entry_date,
            description=body.description,
            source_type="MANUAL",
            source_id=None,
            reference=body.reference,
            is_posted=True,
            created_by=actor_id,
        )
        db.add(entry)
        await db.flush()

        for ln in body.lines:
            db.add(JournalLine(
                journal_entry_id=entry.id,
                account_code=ln.account_code,
                debit=ln.debit,
                credit=ln.credit,
                memo=ln.memo,
                currency=ln.currency,
            ))

        await db.commit()
        await db.refresh(entry)
        # reload lines
        result = (
            await db.execute(
                select(JournalEntry)
                .where(JournalEntry.id == entry.id)
                .options(selectinload(JournalEntry.lines))
            )
        ).scalar_one()

        await log_action(db, action="ledger.manual_entry", org_id=org_id,
                         actor_user_id=actor_id, target_type="journal_entry",
                         target_id=entry.id, request=request)
        await db.commit()
        return JournalEntryOut.model_validate(result)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_manual_entry failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/trial-balance", response_model=TrialBalanceOut)
async def trial_balance(
    as_of: date = Query(default_factory=date.today),
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """Return debit/credit totals per account up to as_of date."""
    try:
        org_id = _org(ctx)

        # Ensure system accounts exist
        await _ensure_system_accounts(db, org_id)
        await db.commit()

        # Get all accounts
        accounts = (
            await db.execute(
                select(ChartOfAccount)
                .where(ChartOfAccount.org_id == org_id, ChartOfAccount.is_active == True)  # noqa
                .order_by(ChartOfAccount.code)
            )
        ).scalars().all()

        # Sum debits / credits per account_code
        from sqlalchemy import case
        sums = (
            await db.execute(
                select(
                    JournalLine.account_code,
                    func.coalesce(func.sum(JournalLine.debit), 0).label("debit_total"),
                    func.coalesce(func.sum(JournalLine.credit), 0).label("credit_total"),
                )
                .join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id)
                .where(
                    JournalEntry.org_id == org_id,
                    JournalEntry.entry_date <= as_of,
                    JournalEntry.is_posted == True,  # noqa
                )
                .group_by(JournalLine.account_code)
            )
        ).all()

        sums_by_code = {row.account_code: (Decimal(row.debit_total), Decimal(row.credit_total)) for row in sums}

        lines = []
        total_debits = Decimal("0")
        total_credits = Decimal("0")

        for acct in accounts:
            debit_t, credit_t = sums_by_code.get(acct.code, (Decimal("0"), Decimal("0")))
            balance = debit_t - credit_t
            total_debits += debit_t
            total_credits += credit_t
            lines.append(TrialBalanceLine(
                code=acct.code,
                name=acct.name,
                account_type=acct.account_type,
                debit_total=debit_t,
                credit_total=credit_t,
                balance=balance,
            ))

        return TrialBalanceOut(
            as_of=as_of,
            lines=lines,
            total_debits=total_debits,
            total_credits=total_credits,
            is_balanced=abs(total_debits - total_credits) < Decimal("0.01"),
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"trial_balance failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/backfill", response_model=BackfillResult)
async def backfill_ledger(
    request: Request,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """One-shot idempotent backfill: creates journal entries for all existing invoices,
    payments, and approved expenses. Safe to call multiple times — already-posted
    sources are skipped via the UniqueConstraint on (org_id, source_type, source_id).

    Requires OWNER role.
    """
    try:
        _, member = ctx
        if member.role != OrgRole.OWNER:
            raise HTTPException(status_code=403, detail="Owner only")

        org_id = _org(ctx)
        await _ensure_system_accounts(db, org_id)
        await db.commit()

        inv_posted = pay_posted = exp_posted = skipped = 0

        # Invoices (SENT, PAID, OVERDUE)
        invoices = (
            await db.execute(
                select(Invoice)
                .where(
                    Invoice.org_id == org_id,
                    Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.PAID, InvoiceStatus.OVERDUE]),
                )
                .options(selectinload(Invoice.line_items))
            )
        ).scalars().all()

        for inv in invoices:
            result = await ledger_svc.post_invoice(db, inv)
            if result:
                inv_posted += 1
            else:
                skipped += 1
        await db.commit()

        # Payments
        payments = (
            await db.execute(
                select(Payment)
                .where(Payment.org_id == org_id)
            )
        ).scalars().all()

        inv_map = {inv.id: inv for inv in invoices}
        for inv in (
            await db.execute(select(Invoice).where(Invoice.org_id == org_id))
        ).scalars().all():
            inv_map[inv.id] = inv

        for pmt in payments:
            inv = inv_map.get(pmt.invoice_id)
            if not inv:
                skipped += 1
                continue
            result = await ledger_svc.post_payment(db, pmt, inv)
            if result:
                pay_posted += 1
            else:
                skipped += 1
        await db.commit()

        # Approved expenses (eager load category for sie_account)
        from sqlalchemy.orm import selectinload as sl
        from app.models.expenses import ExpenseCategory
        expenses = (
            await db.execute(
                select(Expense)
                .where(
                    Expense.org_id == org_id,
                    Expense.status == ExpenseStatus.APPROVED,
                )
                .options(sl(Expense.category))
            )
        ).scalars().all()

        for exp in expenses:
            result = await ledger_svc.post_expense(db, exp)
            if result:
                exp_posted += 1
            else:
                skipped += 1
        await db.commit()

        await log_action(db, action="ledger.backfill", org_id=org_id,
                         actor_user_id=_actor(ctx), request=request,
                         extra={"invoices": inv_posted, "payments": pay_posted,
                                "expenses": exp_posted, "skipped": skipped})
        await db.commit()

        return BackfillResult(
            invoices_posted=inv_posted,
            payments_posted=pay_posted,
            expenses_posted=exp_posted,
            skipped=skipped,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"backfill_ledger failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
