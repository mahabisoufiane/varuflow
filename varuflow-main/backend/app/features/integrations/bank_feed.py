"""Bank Feed / CSV Import router.

Auto-detects Nordic bank CSV formats (SEB, Handelsbanken, Nordea, SHB).

Endpoints:
  GET    /api/accounting/bank-accounts                        list accounts
  POST   /api/accounting/bank-accounts                        add account
  DELETE /api/accounting/bank-accounts/{id}                   remove
  POST   /api/accounting/bank-accounts/{id}/import-csv        parse + import CSV
  GET    /api/accounting/bank-accounts/{id}/transactions       paginated transactions
  POST   /api/accounting/bank-accounts/{id}/auto-match         run auto-matching
  POST   /api/accounting/bank-transactions/{id}/match          match to invoice/expense/payment
  POST   /api/accounting/bank-transactions/{id}/unmatch        reset to UNMATCHED
  POST   /api/accounting/bank-transactions/{id}/exclude        exclude transaction
  POST   /api/accounting/bank-transactions/{id}/create-expense create expense from debit
  GET    /api/accounting/bank-accounts/{id}/reconciliation     summary (all time)
  GET    /api/accounting/bank-accounts/{id}/reconciliation-report  month-end report
"""
from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module, require_role
from .bank_feed_models import BankAccount, BankTransaction
from app.features.auth.organization import OrgRole

# Bank account data is sensitive financial data — manager-level (ADMIN+).
router = APIRouter(tags=["bank_feed"], dependencies=[Depends(require_module("finance")), Depends(require_role(OrgRole.ADMIN))])
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


# ─── CSV format detection helpers ─────────────────────────────────────────

# Each format maps (date_col, amount_col, description_col, value_date_col|None)
_FORMATS = {
    # SEB: Bokföringsdag;Valutadag;Verifikationsnummer;Text/mottagare;Belopp;Saldo
    "seb": ("Bokföringsdag", "Belopp", "Text/mottagare", "Valutadag"),
    # Handelsbanken: Datum;Transaktionstext;Belopp;Saldo
    "shb": ("Datum", "Belopp", "Transaktionstext", None),
    # Nordea: Bokföringsdag;Belopp;Mottagare/Avsändare;Namn;Rubrik;Meddelande;Egna anteckningar;Saldo
    "nordea": ("Bokföringsdag", "Belopp", "Namn", "Bokföringsdag"),
}

# SHB uses comma-separated amounts like "1 234,56" with space thousands separator
def _parse_amount(raw: str) -> Decimal:
    cleaned = raw.strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"Cannot parse amount: {raw!r}")


def _detect_format(header: list[str]) -> tuple[str, str, str, Optional[str]]:
    header_set = set(h.strip() for h in header)
    for _name, cols in _FORMATS.items():
        if cols[0] in header_set and cols[1] in header_set and cols[2] in header_set:
            return cols  # type: ignore[return-value]
    # Fallback: look for generic column names
    date_col = next((h for h in header if "datum" in h.lower() or "date" in h.lower()), None)
    amount_col = next((h for h in header if "belopp" in h.lower() or "amount" in h.lower()), None)
    desc_col = next((h for h in header if "text" in h.lower() or "desc" in h.lower() or "namn" in h.lower()), None)
    if date_col and amount_col and desc_col:
        return (date_col, amount_col, desc_col, None)
    raise ValueError("Unrecognized CSV format. Supported: SEB, Handelsbanken, Nordea.")


def _parse_date(raw: str) -> date:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {raw!r}")


# ─── Schemas ──────────────────────────────────────────────────────────────

class AccountCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    iban: Optional[str] = Field(None, max_length=34)
    currency: str = Field(default="SEK", max_length=3)


class AccountOut(BaseModel):
    id: uuid.UUID
    name: str
    iban: Optional[str]
    currency: str
    last_synced_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionOut(BaseModel):
    id: uuid.UUID
    transaction_date: date
    value_date: Optional[date]
    amount: Decimal
    description: str
    reference: Optional[str]
    status: str
    matched_type: Optional[str]
    matched_id: Optional[uuid.UUID]
    imported_at: datetime

    model_config = {"from_attributes": True}


class MatchIn(BaseModel):
    matched_type: str = Field(..., pattern="^(INVOICE|EXPENSE|PAYMENT|MANUAL)$")
    matched_id: uuid.UUID


class ReconciliationSummary(BaseModel):
    total_transactions: int
    unmatched_count: int
    matched_count: int
    excluded_count: int
    unmatched_total: Decimal
    period_balance: Decimal


class AutoMatchResult(BaseModel):
    matched: int
    already_matched: int
    unmatched_remaining: int


class ExpenseFromTxIn(BaseModel):
    description: Optional[str] = None
    category_id: Optional[uuid.UUID] = None


class ReconciliationReportLine(BaseModel):
    id: uuid.UUID
    transaction_date: date
    amount: Decimal
    description: str
    reference: Optional[str]
    status: str
    matched_type: Optional[str]
    matched_label: Optional[str]  # e.g. invoice number or expense description


class ReconciliationReport(BaseModel):
    account_id: uuid.UUID
    account_name: str
    month: str              # "YYYY-MM"
    from_date: date
    to_date: date
    opening_balance: Decimal
    closing_balance: Decimal
    total_credits: Decimal
    total_debits: Decimal
    matched_count: int
    unmatched_count: int
    excluded_count: int
    unmatched_items: list[ReconciliationReportLine]
    matched_items: list[ReconciliationReportLine]


# ─── Endpoints ────────────────────────────────────────────────────────────

@router.get("/api/accounting/bank-accounts", response_model=list[AccountOut])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    try:
        org_id = _org(ctx)
        rows = (
            await db.execute(
                select(BankAccount)
                .where(BankAccount.org_id == org_id)
                .order_by(BankAccount.created_at.desc())
            )
        ).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_accounts failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/accounting/bank-accounts", response_model=AccountOut, status_code=201)
async def create_account(
    body: AccountCreate,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)
        acct = BankAccount(
            org_id=org_id,
            name=body.name,
            iban=body.iban,
            currency=body.currency.upper(),
        )
        db.add(acct)
        await db.commit()
        await db.refresh(acct)
        return acct
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_account failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/accounting/bank-accounts/{account_id}", status_code=204)
async def delete_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)
        acct = (
            await db.execute(
                select(BankAccount).where(BankAccount.id == account_id, BankAccount.org_id == org_id)
            )
        ).scalar_one_or_none()
        if not acct:
            raise HTTPException(status_code=404, detail="Bank account not found")
        await db.delete(acct)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"delete_account failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/accounting/bank-accounts/{account_id}/import-csv")
async def import_csv(
    account_id: uuid.UUID,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """Parse and import a Nordic bank CSV file. Silently deduplicates existing rows."""
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)
        acct = (
            await db.execute(
                select(BankAccount).where(BankAccount.id == account_id, BankAccount.org_id == org_id)
            )
        ).scalar_one_or_none()
        if not acct:
            raise HTTPException(status_code=404, detail="Bank account not found")

        raw = await file.read()
        # Try UTF-8 then latin-1 (common for Swedish bank exports)
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")

        # Detect delimiter (semicolon or comma)
        first_line = text.split("\n")[0]
        delimiter = ";" if first_line.count(";") >= first_line.count(",") else ","

        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        header = reader.fieldnames or []
        date_col, amount_col, desc_col, vdate_col = _detect_format(header)

        imported = 0
        skipped = 0
        for row in reader:
            raw_date = row.get(date_col, "").strip()
            raw_amount = row.get(amount_col, "").strip()
            raw_desc = row.get(desc_col, "").strip()
            if not raw_date or not raw_amount or not raw_desc:
                continue
            try:
                tx_date = _parse_date(raw_date)
                amount = _parse_amount(raw_amount)
            except ValueError:
                skipped += 1
                continue

            value_date: Optional[date] = None
            if vdate_col and row.get(vdate_col, "").strip():
                try:
                    value_date = _parse_date(row[vdate_col].strip())
                except ValueError:
                    pass

            # Attempt insert; on unique constraint violation skip silently
            try:
                tx = BankTransaction(
                    bank_account_id=account_id,
                    org_id=org_id,
                    transaction_date=tx_date,
                    value_date=value_date,
                    amount=amount,
                    description=raw_desc,
                )
                db.add(tx)
                await db.flush()
                imported += 1
            except Exception:
                await db.rollback()
                skipped += 1
                continue

        acct.last_synced_at = datetime.now(timezone.utc)
        await db.commit()
        return {"imported": imported, "skipped": skipped}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"import_csv failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/accounting/bank-accounts/{account_id}/transactions", response_model=list[TransactionOut])
async def list_transactions(
    account_id: uuid.UUID,
    status_filter: Optional[str] = Query(None, alias="status"),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    try:
        org_id = _org(ctx)
        q = select(BankTransaction).where(
            BankTransaction.bank_account_id == account_id,
            BankTransaction.org_id == org_id,
        )
        if status_filter:
            q = q.where(BankTransaction.status == status_filter.upper())
        if from_date:
            q = q.where(BankTransaction.transaction_date >= from_date)
        if to_date:
            q = q.where(BankTransaction.transaction_date <= to_date)
        q = q.order_by(BankTransaction.transaction_date.desc()).offset((page - 1) * per_page).limit(per_page)
        rows = (await db.execute(q)).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_transactions failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/accounting/bank-transactions/{tx_id}/match", response_model=TransactionOut)
async def match_transaction(
    tx_id: uuid.UUID,
    body: MatchIn,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)
        tx = (
            await db.execute(
                select(BankTransaction).where(BankTransaction.id == tx_id, BankTransaction.org_id == org_id)
            )
        ).scalar_one_or_none()
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")
        tx.status = "MATCHED"
        tx.matched_type = body.matched_type
        tx.matched_id = body.matched_id
        await db.commit()
        await db.refresh(tx)
        return tx
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"match_transaction failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/accounting/bank-transactions/{tx_id}/exclude", response_model=TransactionOut)
async def exclude_transaction(
    tx_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)
        tx = (
            await db.execute(
                select(BankTransaction).where(BankTransaction.id == tx_id, BankTransaction.org_id == org_id)
            )
        ).scalar_one_or_none()
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")
        tx.status = "EXCLUDED"
        await db.commit()
        await db.refresh(tx)
        return tx
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"exclude_transaction failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/accounting/bank-accounts/{account_id}/reconciliation", response_model=ReconciliationSummary)
async def reconciliation_summary(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    try:
        org_id = _org(ctx)
        rows = (
            await db.execute(
                select(BankTransaction).where(
                    BankTransaction.bank_account_id == account_id,
                    BankTransaction.org_id == org_id,
                )
            )
        ).scalars().all()
        total = len(rows)
        unmatched = [r for r in rows if r.status == "UNMATCHED"]
        matched = [r for r in rows if r.status == "MATCHED"]
        excluded = [r for r in rows if r.status == "EXCLUDED"]
        return ReconciliationSummary(
            total_transactions=total,
            unmatched_count=len(unmatched),
            matched_count=len(matched),
            excluded_count=len(excluded),
            unmatched_total=sum((Decimal(str(r.amount)) for r in unmatched), Decimal("0")),
            period_balance=sum((Decimal(str(r.amount)) for r in rows), Decimal("0")),
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"reconciliation_summary failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ─── Auto-match ───────────────────────────────────────────────────────────────

@router.post("/api/accounting/bank-accounts/{account_id}/auto-match", response_model=AutoMatchResult)
async def auto_match(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """
    Attempt to auto-match all UNMATCHED transactions in the account.

    Matching criteria (all must pass):
      1. Transaction is a credit (amount > 0)
      2. An unpaid invoice exists with total_sek == abs(amount) (within 1 SEK rounding)
      3. The invoice due_date is within ±14 days of the transaction date
      4. OR the invoice number appears in the transaction description/reference
    First matching invoice wins. Ties broken by smallest date delta.
    """
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)

        # Verify account belongs to org
        acct = (await db.execute(
            select(BankAccount).where(BankAccount.id == account_id, BankAccount.org_id == org_id)
        )).scalar_one_or_none()
        if not acct:
            raise HTTPException(404, "Bank account not found")

        from app.features.invoicing.models import Invoice

        unmatched_txs = (await db.execute(
            select(BankTransaction).where(
                BankTransaction.bank_account_id == account_id,
                BankTransaction.org_id == org_id,
                BankTransaction.status == "UNMATCHED",
                BankTransaction.amount > 0,  # credits only
            )
        )).scalars().all()

        # Fetch all outstanding invoices for the org (SENT or OVERDUE)
        invoices = (await db.execute(
            select(Invoice).where(
                Invoice.org_id == org_id,
                Invoice.status.in_(["SENT", "OVERDUE"]),
            )
        )).scalars().all()

        # Build invoice lookup by amount bucket
        inv_by_amount: dict[int, list[Invoice]] = {}
        for inv in invoices:
            bucket = int(round(float(inv.total_sek)))
            inv_by_amount.setdefault(bucket, []).append(inv)

        matched_count = 0
        already_matched = 0

        for tx in unmatched_txs:
            tx_amount = float(tx.amount)
            bucket = int(round(tx_amount))
            candidates = inv_by_amount.get(bucket, []) + inv_by_amount.get(bucket - 1, []) + inv_by_amount.get(bucket + 1, [])

            best: Optional[Invoice] = None
            best_delta = 9999

            for inv in candidates:
                inv_amount = float(inv.total_sek)
                # 1. Amount must match within 1 SEK
                if abs(tx_amount - inv_amount) > 1.0:
                    continue
                # 2. Date within ±14 days OR reference match
                date_delta = abs((tx.transaction_date - inv.due_date).days) if inv.due_date else 30
                ref_match = (
                    (inv.invoice_number and inv.invoice_number.lower() in (tx.description or "").lower())
                    or (inv.invoice_number and inv.invoice_number.lower() in (tx.reference or "").lower())
                )
                if date_delta <= 14 or ref_match:
                    score = 0 if ref_match else date_delta
                    if score < best_delta:
                        best = inv
                        best_delta = score

            if best:
                tx.status = "MATCHED"
                tx.matched_type = "INVOICE"
                tx.matched_id = best.id
                matched_count += 1

        await db.commit()

        remaining = (await db.execute(
            select(func.count()).where(
                BankTransaction.bank_account_id == account_id,
                BankTransaction.org_id == org_id,
                BankTransaction.status == "UNMATCHED",
            )
        )).scalar_one()

        return AutoMatchResult(
            matched=matched_count,
            already_matched=already_matched,
            unmatched_remaining=remaining,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"auto_match failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ─── Unmatch ──────────────────────────────────────────────────────────────────

@router.post("/api/accounting/bank-transactions/{tx_id}/unmatch", response_model=TransactionOut)
async def unmatch_transaction(
    tx_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """Reset a MATCHED or EXCLUDED transaction back to UNMATCHED."""
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)
        tx = (await db.execute(
            select(BankTransaction).where(BankTransaction.id == tx_id, BankTransaction.org_id == org_id)
        )).scalar_one_or_none()
        if not tx:
            raise HTTPException(404, "Transaction not found")
        tx.status = "UNMATCHED"
        tx.matched_type = None
        tx.matched_id = None
        await db.commit()
        await db.refresh(tx)
        return tx
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"unmatch_transaction failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ─── Create expense from transaction ─────────────────────────────────────────

@router.post("/api/accounting/bank-transactions/{tx_id}/create-expense", response_model=TransactionOut)
async def create_expense_from_tx(
    tx_id: uuid.UUID,
    body: ExpenseFromTxIn,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """
    Create an Expense record from an unmatched debit transaction (amount < 0),
    then mark the transaction as MATCHED → EXPENSE.
    """
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)
        tx = (await db.execute(
            select(BankTransaction).where(BankTransaction.id == tx_id, BankTransaction.org_id == org_id)
        )).scalar_one_or_none()
        if not tx:
            raise HTTPException(404, "Transaction not found")
        if tx.amount >= 0:
            raise HTTPException(422, "Only debit transactions (amount < 0) can be converted to expenses")

        from app.features.expenses.models import Expense, ExpenseStatus

        exp = Expense(
            org_id=org_id,
            amount=abs(Decimal(str(tx.amount))).quantize(Decimal("0.01")),
            expense_date=tx.transaction_date,
            description=body.description or tx.description,
            status=ExpenseStatus.APPROVED,
            category_id=body.category_id,
            approval_required=False,
        )
        db.add(exp)
        await db.flush()

        tx.status = "MATCHED"
        tx.matched_type = "EXPENSE"
        tx.matched_id = exp.id
        await db.commit()
        await db.refresh(tx)
        return tx
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_expense_from_tx failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ─── Month-end reconciliation report ─────────────────────────────────────────

@router.get("/api/accounting/bank-accounts/{account_id}/reconciliation-report",
            response_model=ReconciliationReport)
async def reconciliation_report(
    account_id: uuid.UUID,
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$", description="YYYY-MM"),
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """
    Month-end reconciliation report for a single month.
    Returns matched/unmatched detail with labels, and opening/closing balance.
    """
    try:
        org_id = _org(ctx)
        acct = (await db.execute(
            select(BankAccount).where(BankAccount.id == account_id, BankAccount.org_id == org_id)
        )).scalar_one_or_none()
        if not acct:
            raise HTTPException(404, "Bank account not found")

        year, mo = int(month[:4]), int(month[5:])
        from calendar import monthrange
        last_day = monthrange(year, mo)[1]
        from_d = date(year, mo, 1)
        to_d = date(year, mo, last_day)

        # Opening balance = sum of all transactions before from_d
        opening_row = (await db.execute(
            select(func.coalesce(func.sum(BankTransaction.amount), 0))
            .where(
                BankTransaction.bank_account_id == account_id,
                BankTransaction.org_id == org_id,
                BankTransaction.transaction_date < from_d,
            )
        )).scalar_one()
        opening_balance = Decimal(str(opening_row)).quantize(Decimal("0.01"))

        # Transactions in the month
        txs = (await db.execute(
            select(BankTransaction).where(
                BankTransaction.bank_account_id == account_id,
                BankTransaction.org_id == org_id,
                BankTransaction.transaction_date >= from_d,
                BankTransaction.transaction_date <= to_d,
            ).order_by(BankTransaction.transaction_date)
        )).scalars().all()

        # Fetch invoice numbers for matched invoices
        matched_invoice_ids = [
            tx.matched_id for tx in txs
            if tx.matched_type == "INVOICE" and tx.matched_id
        ]
        matched_expense_ids = [
            tx.matched_id for tx in txs
            if tx.matched_type == "EXPENSE" and tx.matched_id
        ]

        inv_labels: dict[uuid.UUID, str] = {}
        if matched_invoice_ids:
            from app.features.invoicing.models import Invoice
            inv_rows = (await db.execute(
                select(Invoice.id, Invoice.invoice_number).where(Invoice.id.in_(matched_invoice_ids))
            )).all()
            inv_labels = {r.id: r.invoice_number for r in inv_rows}

        exp_labels: dict[uuid.UUID, str] = {}
        if matched_expense_ids:
            from app.features.expenses.models import Expense
            exp_rows = (await db.execute(
                select(Expense.id, Expense.description).where(Expense.id.in_(matched_expense_ids))
            )).all()
            exp_labels = {r.id: r.description or "Expense" for r in exp_rows}

        total_credits = Decimal("0")
        total_debits = Decimal("0")
        unmatched_items: list[ReconciliationReportLine] = []
        matched_items: list[ReconciliationReportLine] = []

        for tx in txs:
            amt = Decimal(str(tx.amount)).quantize(Decimal("0.01"))
            if amt > 0:
                total_credits += amt
            else:
                total_debits += abs(amt)

            # Build matched label
            label: Optional[str] = None
            if tx.matched_id and tx.matched_type == "INVOICE":
                label = f"Invoice {inv_labels.get(tx.matched_id, str(tx.matched_id))}"
            elif tx.matched_id and tx.matched_type == "EXPENSE":
                label = f"Expense: {exp_labels.get(tx.matched_id, str(tx.matched_id))}"
            elif tx.matched_type == "MANUAL":
                label = "Manual match"

            line = ReconciliationReportLine(
                id=tx.id,
                transaction_date=tx.transaction_date,
                amount=amt,
                description=tx.description,
                reference=tx.reference,
                status=tx.status,
                matched_type=tx.matched_type,
                matched_label=label,
            )
            if tx.status == "UNMATCHED":
                unmatched_items.append(line)
            else:
                matched_items.append(line)

        closing_balance = opening_balance + total_credits - total_debits

        return ReconciliationReport(
            account_id=acct.id,
            account_name=acct.name,
            month=month,
            from_date=from_d,
            to_date=to_d,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_credits=total_credits,
            total_debits=total_debits,
            matched_count=sum(1 for t in txs if t.status == "MATCHED"),
            unmatched_count=sum(1 for t in txs if t.status == "UNMATCHED"),
            excluded_count=sum(1 for t in txs if t.status == "EXCLUDED"),
            unmatched_items=unmatched_items,
            matched_items=matched_items,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"reconciliation_report failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
