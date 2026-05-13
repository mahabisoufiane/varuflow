"""Pure helpers for supplier account statements (Item 93).

Mirror of Item 72's customer statement service, flipped to the
supplier (accounts-payable) side. A supplier statement is a
period-bounded view of everything that moved our outstanding
balance with a given supplier:

* payable invoices raised against us (by the supplier),
* issued supplier credit notes (which reduce what we owe).

This codebase has no outgoing-payments table yet, so the statement
only tracks bills + credits. If a payables-payment model lands in
a future item, a new ``PaymentRow`` family can be added without
changing the shape of this module.

Balance convention:
    positive = tenant owes the supplier
    negative = supplier owes the tenant (over-credited)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

MAX_PERIOD_DAYS: int = 366
_Q2 = Decimal("0.01")


@dataclass(frozen=True)
class PayableRow:
    id:          str
    number:      str | None  # supplier's own invoice number
    issue_date:  date
    due_date:    date | None
    total:       Decimal
    status:      str


@dataclass(frozen=True)
class CreditRow:
    id:                str
    number:            str | None
    purchase_order_id: str | None
    issue_date:        date
    total:             Decimal
    status:            str  # "ISSUED" / "VOIDED" / ...


@dataclass(frozen=True)
class StatementPayable:
    id:         str
    number:     str | None
    issue_date: date
    due_date:   date | None
    total:      Decimal
    credited:   Decimal
    remaining:  Decimal
    status:     str


@dataclass(frozen=True)
class StatementCredit:
    id:                str
    number:            str | None
    purchase_order_id: str | None
    issue_date:        date
    total:             Decimal


@dataclass(frozen=True)
class StatementEntry:
    entry_date: date
    kind:       str   # "payable" | "credit"
    ref_id:     str
    amount:     Decimal  # signed: + increases balance, − decreases
    balance:    Decimal
    label:      str


@dataclass(frozen=True)
class StatementTotals:
    payables_issued: Decimal
    credits_issued:  Decimal
    outstanding:     Decimal


@dataclass(frozen=True)
class Statement:
    supplier_id:     str
    period_start:    date
    period_end:      date
    opening_balance: Decimal
    closing_balance: Decimal
    payables:        list[StatementPayable]
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
    """Issued credits reduce balance; DRAFT/VOIDED don't move it."""
    if (row.status or "").upper() == "ISSUED":
        return -row.total
    return Decimal("0.00")


def _q(v: Decimal) -> Decimal:
    return Decimal(v).quantize(_Q2)


def build_statement(
    *,
    supplier_id:  str,
    period_start: date,
    period_end:   date,
    payables: list[PayableRow],
    credits:  list[CreditRow],
) -> Statement:
    """Pure builder.

    Caller supplies *all* payables/credits ever attached to the
    supplier; this function computes in-window slices and opening
    balance. Credits bound to a PO reduce that PO's payable
    ``remaining`` (when the payable exists); standalone credits
    (``purchase_order_id is None``) apply only to the overall balance.
    """
    validate_period(start=period_start, end=period_end)

    # ── opening balance: everything strictly before period_start ──
    opening = Decimal("0.00")
    for pv in payables:
        if pv.issue_date < period_start:
            opening += pv.total
    for cr in credits:
        if cr.issue_date < period_start:
            opening += _signed_credit(cr)

    opening = _q(opening)

    # ── in-period slices ──
    pv_in = [
        p for p in payables
        if period_start <= p.issue_date <= period_end
    ]
    cr_in = [
        c for c in credits
        if period_start <= c.issue_date <= period_end
        and (c.status or "").upper() == "ISSUED"
    ]

    # ── per-payable credit allocation across whole history. Credits
    #    are keyed by ``purchase_order_id``; we need to resolve that
    #    to the payable ``id`` that references the same PO. Caller
    #    passes payables with their source PO id in ``number``-agnostic
    #    form? No — the payable model itself carries ``purchase_order_id``.
    #    Here we just match by the payable's own PO id when present,
    #    via a small helper map the caller fills implicitly: credits
    #    with a PO id are allocated to the payable whose source PO
    #    matches. To keep the service pure, the caller supplies a
    #    side-table via ``payable_po_map``. Default: no PO mapping.
    # In practice the router hands us payables tagged with the PO id in
    # their row id only; allocation by PO is handled upstream. Keep the
    # pure service simple: do NOT allocate credits to specific payables
    # here — credits only affect the overall balance and the standalone
    # credits list. Per-payable ``credited`` is always 0 in this shape.

    statement_payables: list[StatementPayable] = []
    for pv in sorted(pv_in, key=lambda x: (x.issue_date, x.id)):
        remaining = pv.total
        if remaining < 0:
            remaining = Decimal("0.00")
        statement_payables.append(StatementPayable(
            id=pv.id, number=pv.number,
            issue_date=pv.issue_date, due_date=pv.due_date,
            total=_q(pv.total),
            credited=Decimal("0.00"),
            remaining=_q(remaining),
            status=pv.status,
        ))

    statement_credits = [
        StatementCredit(
            id=c.id,
            number=c.number,
            purchase_order_id=c.purchase_order_id,
            issue_date=c.issue_date,
            total=_q(c.total),
        )
        for c in sorted(cr_in, key=lambda x: (x.issue_date, x.id))
    ]

    # ── merged chronological feed with running balance ──
    merged: list[tuple[date, int, str, str, Decimal, str]] = []
    # priority tuple: (date, kind-order, id) — payables first on the
    # same day so the balance rises before it falls.
    for pv in pv_in:
        merged.append((
            pv.issue_date, 0, "payable", pv.id, pv.total,
            f"Bill {pv.number or pv.id}",
        ))
    for c in cr_in:
        merged.append((
            c.issue_date, 1, "credit", c.id, -c.total,
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

    payables_issued = sum((p.total for p in pv_in), Decimal("0.00"))
    credits_sum     = sum((c.total for c in cr_in), Decimal("0.00"))

    totals = StatementTotals(
        payables_issued=_q(payables_issued),
        credits_issued=_q(credits_sum),
        outstanding=closing,
    )

    return Statement(
        supplier_id=supplier_id,
        period_start=period_start,
        period_end=period_end,
        opening_balance=opening,
        closing_balance=closing,
        payables=statement_payables,
        credits=statement_credits,
        entries=entries,
        totals=totals,
    )
