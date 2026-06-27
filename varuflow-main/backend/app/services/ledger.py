"""Ledger posting helpers.

Called by invoicing/expense routers to generate balanced journal entries
whenever a bookkeeping event occurs (invoice sent, payment received, etc.).

Each helper is idempotent: if a journal entry for the given source already
exists (source_type + source_id unique constraint), the INSERT is silently
skipped via ON CONFLICT DO NOTHING semantics (checked with a SELECT first).

BAS 2024 account codes used:
  1510  Kundfordringar      (AR / receivables)
  2610  Utgående moms 25%   (output VAT 25%)
  2621  Utgående moms 12%
  2631  Utgående moms 6%
  2640  Ingående moms        (input VAT — expenses)
  3000  Försäljning         (revenue)
  4000  Inköp av varor      (expense / cost)
  1920  Kassa och bank      (bank / cash — cleared on payment)
"""
from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.analytics.accounting_models import JournalEntry, JournalLine
from app.features.invoicing.models import Invoice, Payment

log = logging.getLogger(__name__)

# Map tax rates → output VAT account codes
_OUTPUT_VAT_ACCOUNT: dict[int, str] = {
    25: "2610",
    12: "2621",
    6:  "2631",
}


async def _entry_exists(
    db: AsyncSession, org_id: uuid.UUID, source_type: str, source_id: uuid.UUID
) -> bool:
    row = await db.execute(
        select(JournalEntry.id).where(
            JournalEntry.org_id == org_id,
            JournalEntry.source_type == source_type,
            JournalEntry.source_id == source_id,
        )
    )
    return row.scalar_one_or_none() is not None


async def _commit_entry(
    db: AsyncSession,
    org_id: uuid.UUID,
    entry_date: date,
    description: str,
    source_type: str,
    source_id: uuid.UUID,
    reference: str | None,
    lines: list[dict],
    created_by: uuid.UUID | None = None,
) -> JournalEntry | None:
    """Create a JournalEntry + lines. Returns None if already exists."""
    if await _entry_exists(db, org_id, source_type, source_id):
        return None

    entry = JournalEntry(
        org_id=org_id,
        entry_date=entry_date,
        description=description,
        source_type=source_type,
        source_id=source_id,
        reference=reference,
        is_posted=True,
        created_by=created_by,
    )
    db.add(entry)
    await db.flush()  # populate entry.id

    for line in lines:
        db.add(
            JournalLine(
                journal_entry_id=entry.id,
                account_code=line["account_code"],
                debit=line.get("debit", Decimal("0")),
                credit=line.get("credit", Decimal("0")),
                memo=line.get("memo"),
                currency=line.get("currency", "SEK"),
            )
        )
    return entry


async def post_invoice(
    db: AsyncSession,
    invoice: Invoice,
    created_by: uuid.UUID | None = None,
) -> JournalEntry | None:
    """Post an invoice to the ledger.

    Debit  1510 Kundfordringar (total_sek — full AR including VAT)
    Credit 3000 Försäljning    (subtotal)
    Credit 26xx Utgående moms  (vat_amount, split by tax rate if line items present)

    We use a single VAT line at the invoice level for simplicity; if the
    invoice has multiple tax rates the caller should use post_invoice_detailed.
    """
    total = Decimal(str(invoice.total_sek))
    subtotal = Decimal(str(invoice.subtotal))
    vat = Decimal(str(invoice.vat_amount))
    currency = invoice.currency or "SEK"

    # Determine primary VAT account — default to 25%
    vat_account = "2610"
    try:
        from app.features.invoicing.models import InvoiceLineItem  # local import to avoid circular
        lines_q = await db.execute(
            select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice.id)
        )
        line_items = lines_q.scalars().all()
        if line_items:
            # Use the most common tax rate
            from collections import Counter
            rate_counts = Counter(int(li.tax_rate) for li in line_items)
            dominant_rate = rate_counts.most_common(1)[0][0]
            vat_account = _OUTPUT_VAT_ACCOUNT.get(dominant_rate, "2610")
    except Exception:
        pass

    journal_lines = [
        {"account_code": "1510", "debit": total, "credit": Decimal("0"), "memo": f"AR {invoice.invoice_number}", "currency": currency},
        {"account_code": "3000", "debit": Decimal("0"), "credit": subtotal, "memo": f"Revenue {invoice.invoice_number}", "currency": currency},
        {"account_code": vat_account, "debit": Decimal("0"), "credit": vat, "memo": f"VAT {invoice.invoice_number}", "currency": currency},
    ]

    return await _commit_entry(
        db=db,
        org_id=invoice.org_id,
        entry_date=invoice.issue_date,
        description=f"Invoice {invoice.invoice_number}",
        source_type="INVOICE",
        source_id=invoice.id,
        reference=invoice.invoice_number,
        lines=journal_lines,
        created_by=created_by,
    )


async def post_payment(
    db: AsyncSession,
    payment: Payment,
    invoice: Invoice,
    created_by: uuid.UUID | None = None,
) -> JournalEntry | None:
    """Post a payment receipt to the ledger.

    Debit  1920 Kassa och bank  (cash received)
    Credit 1510 Kundfordringar  (clear AR)
    """
    amount = Decimal(str(payment.amount))
    currency = payment.currency or "SEK"
    inv_num = invoice.invoice_number

    journal_lines = [
        {"account_code": "1920", "debit": amount, "credit": Decimal("0"), "memo": f"Payment for {inv_num}", "currency": currency},
        {"account_code": "1510", "debit": Decimal("0"), "credit": amount, "memo": f"Clear AR {inv_num}", "currency": currency},
    ]

    return await _commit_entry(
        db=db,
        org_id=payment.org_id,
        entry_date=payment.payment_date,
        description=f"Payment for invoice {inv_num}",
        source_type="PAYMENT",
        source_id=payment.id,
        reference=inv_num,
        lines=journal_lines,
        created_by=created_by,
    )


async def post_expense(
    db: AsyncSession,
    expense,
    created_by: uuid.UUID | None = None,
) -> JournalEntry | None:
    """Post an approved expense to the ledger.

    Debit  4000 (or category sie_account) — cost
    Credit 1920 Kassa och bank             — cash out
    """
    amount = Decimal(str(expense.amount))
    currency = getattr(expense, "currency", "SEK") or "SEK"

    # Use the category's sie_account if available
    expense_account = "4000"
    try:
        if expense.category and expense.category.sie_account:
            expense_account = expense.category.sie_account
    except Exception:
        pass

    journal_lines = [
        {"account_code": expense_account, "debit": amount, "credit": Decimal("0"), "memo": expense.description or "Expense", "currency": currency},
        {"account_code": "1920", "debit": Decimal("0"), "credit": amount, "memo": expense.description or "Expense", "currency": currency},
    ]

    return await _commit_entry(
        db=db,
        org_id=expense.org_id,
        entry_date=expense.expense_date,
        description=expense.description or "Expense",
        source_type="EXPENSE",
        source_id=expense.id,
        reference=None,
        lines=journal_lines,
        created_by=created_by,
    )
