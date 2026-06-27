"""Pure helpers for customer account statements (Item 72).

A *statement* is a period-bounded summary of everything that moved
a customer's outstanding balance — invoices issued, payments
received, credit notes applied — plus the closing balance. No DB
access in this module; the router loads the raw rows and hands
them to :func:`build_statement`.

Shape:

    Statement(
        customer_id, period_start, period_end,
        opening_balance, closing_balance,
        invoices=[StatementInvoice(...)],
        payments=[StatementPayment(...)],
        credits=[StatementCredit(...)],
        entries=[StatementEntry(...)],   # chronological feed
        totals=StatementTotals(...),
    )

Balance convention:
    positive = customer owes the tenant
    negative = tenant owes the customer (over-credited / prepaid)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

MAX_PERIOD_DAYS: int = 366  # one leap year cap to keep the feed bounded
_Q2 = Decimal("0.01")


@dataclass(frozen=True)
class InvoiceRow:
    id:              str
    number:          str | None
    issue_date:      date
    due_date:        date
    total:           Decimal
    status:          str


@dataclass(frozen=True)
class PaymentRow:
    id:           str
    invoice_id:   str | None
    payment_date: date
    amount:       Decimal
    method:       str | None = None


@dataclass(frozen=True)
class CreditRow:
    id:          str
    number:      str | None
    invoice_id:  str | None
    issue_date:  date
    total:       Decimal
    status:      str  # "ISSUED" / "VOIDED" / ...


@dataclass(frozen=True)
class StatementInvoice:
    id:         str
    number:     str | None
    issue_date: date
    due_date:   date
    total:      Decimal
    paid:       Decimal
    credited:   Decimal
    remaining:  Decimal
    status:     str


@dataclass(frozen=True)
class StatementPayment:
    id:           str
    invoice_id:   str | None
    payment_date: date
    amount:       Decimal
    method:       str | None


@dataclass(frozen=True)
class StatementCredit:
    id:         str
    number:     str | None
    invoice_id: str | None
    issue_date: date
    total:      Decimal


@dataclass(frozen=True)
class StatementEntry:
    """Single chronological line in the merged feed."""
    entry_date: date
    kind:       str   # "invoice" | "payment" | "credit"
    ref_id:     str
    amount:     Decimal  # signed: + increases balance, − decreases
    balance:    Decimal  # running balance *after* this entry
    label:      str


@dataclass(frozen=True)
class StatementTotals:
    invoices_issued: Decimal
    payments:        Decimal
    credits_issued:  Decimal
    outstanding:     Decimal  # same as closing_balance


@dataclass(frozen=True)
class Statement:
    customer_id:     str
    period_start:    date
    period_end:      date
    opening_balance: Decimal
    closing_balance: Decimal
    invoices:        list[StatementInvoice]
    payments:        list[StatementPayment]
    credits:         list[StatementCredit]
    entries:         list[StatementEntry]
    totals:          StatementTotals


def validate_period(*, start: date, end: date) -> None:
    if not isinstance(start, date) or not isinstance(end, date):
        raise ValueError("period_start and period_end must be dates")
    if end < start:
        raise ValueError("period_end must be on or after period_start")
    if (end - start) > timedelta(days=MAX_PERIOD_DAYS):
        raise ValueError(
            f"period exceeds {MAX_PERIOD_DAYS} days — narrow the window"
        )


def month_bounds(*, year: int, month: int) -> tuple[date, date]:
    if not (1 <= month <= 12):
        raise ValueError("month must be 1..12")
    if not (2000 <= year <= 3000):
        raise ValueError("year out of range")
    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def _signed_credit(row: CreditRow) -> Decimal:
    """Issued credits reduce the balance; others (DRAFT/VOIDED) don't."""
    if (row.status or "").upper() == "ISSUED":
        return -row.total
    return Decimal("0.00")


def _q(v: Decimal) -> Decimal:
    return Decimal(v).quantize(_Q2)


def build_statement(
    *,
    customer_id: str,
    period_start: date,
    period_end:   date,
    invoices: list[InvoiceRow],
    payments: list[PaymentRow],
    credits:  list[CreditRow],
) -> Statement:
    """Pure builder.

    The caller supplies *all* invoices / payments / credits that ever
    belonged to the customer — this function computes what falls
    inside the window and what the opening balance was at the start.
    """
    validate_period(start=period_start, end=period_end)

    # ── opening balance: everything strictly before period_start ──
    opening = Decimal("0.00")
    for inv in invoices:
        if inv.issue_date < period_start:
            opening += inv.total
    for pay in payments:
        if pay.payment_date < period_start:
            opening -= pay.amount
    for cr in credits:
        if cr.issue_date < period_start:
            opening += _signed_credit(cr)

    opening = _q(opening)

    # ── in-period slices ──
    inv_in = [
        i for i in invoices
        if period_start <= i.issue_date <= period_end
    ]
    pay_in = [
        p for p in payments
        if period_start <= p.payment_date <= period_end
    ]
    cr_in = [
        c for c in credits
        if period_start <= c.issue_date <= period_end
        and (c.status or "").upper() == "ISSUED"
    ]

    # ── per-invoice allocation (across the whole history, not just
    #    the window — a payment before the window still reduces the
    #    invoice's ``remaining``) ──
    paid_by_inv: dict[str, Decimal] = {}
    for p in payments:
        if p.invoice_id is None:
            continue
        paid_by_inv[p.invoice_id] = (
            paid_by_inv.get(p.invoice_id, Decimal("0.00")) + p.amount
        )
    cred_by_inv: dict[str, Decimal] = {}
    for c in credits:
        if c.invoice_id is None:
            continue
        if (c.status or "").upper() != "ISSUED":
            continue
        cred_by_inv[c.invoice_id] = (
            cred_by_inv.get(c.invoice_id, Decimal("0.00")) + c.total
        )

    statement_invoices: list[StatementInvoice] = []
    for inv in sorted(inv_in, key=lambda x: (x.issue_date, x.id)):
        paid     = paid_by_inv.get(inv.id, Decimal("0.00"))
        credited = cred_by_inv.get(inv.id, Decimal("0.00"))
        remaining = inv.total - paid - credited
        if remaining < 0:
            remaining = Decimal("0.00")
        statement_invoices.append(StatementInvoice(
            id=inv.id, number=inv.number,
            issue_date=inv.issue_date, due_date=inv.due_date,
            total=_q(inv.total),
            paid=_q(paid),
            credited=_q(credited),
            remaining=_q(remaining),
            status=inv.status,
        ))

    statement_payments = [
        StatementPayment(
            id=p.id,
            invoice_id=p.invoice_id,
            payment_date=p.payment_date,
            amount=_q(p.amount),
            method=p.method,
        )
        for p in sorted(pay_in, key=lambda x: (x.payment_date, x.id))
    ]
    statement_credits = [
        StatementCredit(
            id=c.id,
            number=c.number,
            invoice_id=c.invoice_id,
            issue_date=c.issue_date,
            total=_q(c.total),
        )
        for c in sorted(cr_in, key=lambda x: (x.issue_date, x.id))
    ]

    # ── merged chronological feed with running balance ──
    merged: list[tuple[date, int, str, str, Decimal, str]] = []
    # priority tuple: (date, kind-order, id) — invoices first on the
    # same day so the balance rises before it falls.
    for inv in inv_in:
        merged.append((
            inv.issue_date, 0, "invoice", inv.id, inv.total,
            f"Invoice {inv.number or inv.id}",
        ))
    for p in pay_in:
        merged.append((
            p.payment_date, 1, "payment", p.id, -p.amount,
            f"Payment {p.id}",
        ))
    for c in cr_in:
        merged.append((
            c.issue_date, 2, "credit", c.id, -c.total,
            f"Credit note {c.number or c.id}",
        ))
    merged.sort(key=lambda t: (t[0], t[1], t[3]))

    entries: list[StatementEntry] = []
    balance = opening
    for d, _, kind, ref, amount, label in merged:
        balance += amount
        entries.append(StatementEntry(
            entry_date=d, kind=kind, ref_id=ref,
            amount=_q(amount),
            balance=_q(balance),
            label=label,
        ))

    closing = _q(balance)

    invoices_issued = sum((i.total for i in inv_in), Decimal("0.00"))
    payments_sum    = sum((p.amount for p in pay_in), Decimal("0.00"))
    credits_sum     = sum((c.total for c in cr_in),  Decimal("0.00"))

    totals = StatementTotals(
        invoices_issued=_q(invoices_issued),
        payments=_q(payments_sum),
        credits_issued=_q(credits_sum),
        outstanding=closing,
    )

    return Statement(
        customer_id=customer_id,
        period_start=period_start,
        period_end=period_end,
        opening_balance=opening,
        closing_balance=closing,
        invoices=statement_invoices,
        payments=statement_payments,
        credits=statement_credits,
        entries=entries,
        totals=totals,
    )
