"""Item 72 — Customer account statements."""
from __future__ import annotations

import pathlib
from datetime import date
from decimal import Decimal

import pytest

from app.services import customer_statement as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(p: str) -> str:
    return (_BACKEND_ROOT / p).read_text()


SERVICE_SRC = _read("app/services/customer_statement.py")
ROUTER_SRC  = _read("app/routers/customer_statements.py")
MAIN_SRC    = _read("app/main.py")


def _inv(
    id_: str, *, issue: date, total: str,
    number: str | None = None, due: date | None = None,
    status: str = "SENT",
) -> svc.InvoiceRow:
    return svc.InvoiceRow(
        id=id_, number=number, issue_date=issue,
        due_date=due or issue, total=Decimal(total), status=status,
    )


def _pay(
    id_: str, *, inv: str | None, at: date, amount: str,
    method: str | None = None,
) -> svc.PaymentRow:
    return svc.PaymentRow(
        id=id_, invoice_id=inv, payment_date=at,
        amount=Decimal(amount), method=method,
    )


def _cr(
    id_: str, *, inv: str | None, at: date, total: str,
    status: str = "ISSUED", number: str | None = None,
) -> svc.CreditRow:
    return svc.CreditRow(
        id=id_, number=number, invoice_id=inv,
        issue_date=at, total=Decimal(total), status=status,
    )


# ── Period validation ────────────────────────────────────────────────────


def test_validate_period_ok():
    svc.validate_period(start=date(2026, 1, 1), end=date(2026, 1, 31))
    svc.validate_period(start=date(2026, 1, 1), end=date(2026, 1, 1))


def test_validate_period_rejects_reverse():
    with pytest.raises(ValueError, match="on or after"):
        svc.validate_period(
            start=date(2026, 2, 1), end=date(2026, 1, 31),
        )


def test_validate_period_rejects_too_long():
    with pytest.raises(ValueError, match="exceeds"):
        svc.validate_period(
            start=date(2024, 1, 1), end=date(2026, 1, 1),
        )


def test_validate_period_rejects_non_dates():
    with pytest.raises(ValueError):
        svc.validate_period(start="2026-01-01", end=date(2026, 1, 31))  # type: ignore[arg-type]


# ── month_bounds ─────────────────────────────────────────────────────────


def test_month_bounds_standard():
    s, e = svc.month_bounds(year=2026, month=3)
    assert s == date(2026, 3, 1)
    assert e == date(2026, 3, 31)


def test_month_bounds_february_non_leap():
    s, e = svc.month_bounds(year=2026, month=2)
    assert s == date(2026, 2, 1)
    assert e == date(2026, 2, 28)


def test_month_bounds_february_leap():
    s, e = svc.month_bounds(year=2024, month=2)
    assert e == date(2024, 2, 29)


def test_month_bounds_december():
    s, e = svc.month_bounds(year=2026, month=12)
    assert s == date(2026, 12, 1)
    assert e == date(2026, 12, 31)


def test_month_bounds_rejects_bad_month():
    for m in (0, 13, -1):
        with pytest.raises(ValueError):
            svc.month_bounds(year=2026, month=m)


def test_month_bounds_rejects_bad_year():
    with pytest.raises(ValueError):
        svc.month_bounds(year=1999, month=6)


# ── Statement builder ────────────────────────────────────────────────────


def test_build_empty_period_zero_balances():
    stmt = svc.build_statement(
        customer_id="cust-1",
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        invoices=[], payments=[], credits=[],
    )
    assert stmt.opening_balance == Decimal("0.00")
    assert stmt.closing_balance == Decimal("0.00")
    assert stmt.invoices == []
    assert stmt.entries == []
    assert stmt.totals.outstanding == Decimal("0.00")


def test_build_opening_balance_from_prior_invoices():
    stmt = svc.build_statement(
        customer_id="c",
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        invoices=[_inv("i1", issue=date(2026, 2, 15), total="1000")],
        payments=[_pay("p1", inv="i1", at=date(2026, 2, 20), amount="300")],
        credits=[],
    )
    # Opening = 1000 − 300 = 700
    assert stmt.opening_balance == Decimal("700.00")
    # Nothing happened in the window.
    assert stmt.closing_balance == Decimal("700.00")
    assert stmt.entries == []


def test_build_in_period_invoice_and_payment_balance():
    stmt = svc.build_statement(
        customer_id="c",
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        invoices=[_inv("i1", issue=date(2026, 3, 5), total="500")],
        payments=[_pay("p1", inv="i1", at=date(2026, 3, 20), amount="200")],
        credits=[],
    )
    assert stmt.opening_balance == Decimal("0.00")
    assert stmt.closing_balance == Decimal("300.00")
    assert len(stmt.entries) == 2
    # Invoice first (kind priority), then payment.
    assert stmt.entries[0].kind == "invoice"
    assert stmt.entries[0].balance == Decimal("500.00")
    assert stmt.entries[1].kind == "payment"
    assert stmt.entries[1].balance == Decimal("300.00")


def test_build_issued_credit_reduces_balance():
    stmt = svc.build_statement(
        customer_id="c",
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        invoices=[_inv("i1", issue=date(2026, 3, 5), total="500")],
        payments=[],
        credits=[_cr("c1", inv="i1", at=date(2026, 3, 10),
                     total="100", status="ISSUED")],
    )
    assert stmt.closing_balance == Decimal("400.00")


def test_build_draft_and_voided_credits_ignored():
    stmt = svc.build_statement(
        customer_id="c",
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        invoices=[_inv("i1", issue=date(2026, 3, 5), total="500")],
        payments=[],
        credits=[
            _cr("c1", inv="i1", at=date(2026, 3, 10),
                total="100", status="DRAFT"),
            _cr("c2", inv="i1", at=date(2026, 3, 12),
                total="50",  status="VOIDED"),
        ],
    )
    assert stmt.closing_balance == Decimal("500.00")
    # In-period credits list only includes ISSUED.
    assert stmt.credits == []


def test_build_invoice_remaining_zero_when_over_paid():
    # Prior payment exceeds the invoice — remaining floors at zero.
    stmt = svc.build_statement(
        customer_id="c",
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        invoices=[_inv("i1", issue=date(2026, 3, 5), total="100")],
        payments=[
            _pay("p1", inv="i1", at=date(2026, 3, 10), amount="150"),
        ],
        credits=[],
    )
    assert stmt.invoices[0].paid == Decimal("150.00")
    assert stmt.invoices[0].remaining == Decimal("0.00")


def test_build_remaining_accounts_for_prior_payment():
    # Payment before the window still reduces the in-period
    # invoice's remaining.
    stmt = svc.build_statement(
        customer_id="c",
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        invoices=[_inv("i1", issue=date(2026, 3, 5), total="500")],
        payments=[
            _pay("p1", inv="i1", at=date(2026, 2, 28), amount="200"),
        ],
        credits=[],
    )
    inv = stmt.invoices[0]
    assert inv.paid == Decimal("200.00")
    assert inv.remaining == Decimal("300.00")
    # Opening balance = −200 (payment before invoice). Closing = 300.
    assert stmt.opening_balance == Decimal("-200.00")
    assert stmt.closing_balance == Decimal("300.00")


def test_build_entry_order_same_day_invoice_before_payment():
    # Same date — invoice should land before the payment in the feed
    # so the running balance rises before it falls.
    stmt = svc.build_statement(
        customer_id="c",
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        invoices=[_inv("i1", issue=date(2026, 3, 15), total="200")],
        payments=[_pay("p1", inv="i1", at=date(2026, 3, 15),
                       amount="200")],
        credits=[],
    )
    kinds = [e.kind for e in stmt.entries]
    assert kinds == ["invoice", "payment"]
    assert stmt.entries[0].balance == Decimal("200.00")
    assert stmt.entries[1].balance == Decimal("0.00")


def test_build_totals_match_entry_amounts():
    stmt = svc.build_statement(
        customer_id="c",
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        invoices=[
            _inv("i1", issue=date(2026, 3, 5),  total="500"),
            _inv("i2", issue=date(2026, 3, 20), total="300"),
        ],
        payments=[_pay("p1", inv="i1", at=date(2026, 3, 25),
                       amount="100")],
        credits=[_cr("c1", inv="i2", at=date(2026, 3, 28),
                     total="50", status="ISSUED")],
    )
    t = stmt.totals
    assert t.invoices_issued == Decimal("800.00")
    assert t.payments        == Decimal("100.00")
    assert t.credits_issued  == Decimal("50.00")
    assert t.outstanding     == Decimal("650.00")
    assert stmt.closing_balance == t.outstanding


def test_build_invoices_list_scoped_to_period():
    stmt = svc.build_statement(
        customer_id="c",
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        invoices=[
            _inv("old", issue=date(2026, 1, 10), total="100"),
            _inv("mid", issue=date(2026, 3, 15), total="200"),
            _inv("new", issue=date(2026, 4, 10), total="300"),
        ],
        payments=[], credits=[],
    )
    assert [i.id for i in stmt.invoices] == ["mid"]


def test_build_entries_chronological():
    stmt = svc.build_statement(
        customer_id="c",
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        invoices=[
            _inv("i1", issue=date(2026, 3, 20), total="100"),
            _inv("i2", issue=date(2026, 3, 5),  total="200"),
        ],
        payments=[_pay("p1", inv="i2", at=date(2026, 3, 10),
                       amount="50")],
        credits=[],
    )
    dates = [e.entry_date for e in stmt.entries]
    assert dates == sorted(dates)


def test_build_credits_without_invoice_still_reduce_balance():
    # Standalone (no invoice_id) ISSUED credit.
    stmt = svc.build_statement(
        customer_id="c",
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        invoices=[_inv("i1", issue=date(2026, 3, 5), total="500")],
        payments=[],
        credits=[_cr("c1", inv=None, at=date(2026, 3, 10),
                     total="80", status="ISSUED")],
    )
    assert stmt.closing_balance == Decimal("420.00")


# ── Router source contract ───────────────────────────────────────────────


def test_router_prefix_and_endpoints():
    assert 'prefix="/api/customer-statements"' in ROUTER_SRC
    assert '@router.get("/{customer_id}"' in ROUTER_SRC
    assert '@router.get("/{customer_id}/month"' in ROUTER_SRC


def test_router_tenant_scopes_every_query():
    # Three top-level data queries + the customer-belongs check.
    assert "Invoice.org_id == org_id" in ROUTER_SRC
    assert "Payment.org_id == org_id" in ROUTER_SRC
    assert "CreditNote.org_id == org_id" in ROUTER_SRC
    assert "Customer.org_id == org_id" in ROUTER_SRC


def test_router_audit_action_with_request_kwarg():
    assert '"customer_statement.viewed"' in ROUTER_SRC
    assert ROUTER_SRC.count("request=request") >= 2
    assert "closing_balance" in ROUTER_SRC


def test_router_uses_pure_service():
    assert "build_statement(" in ROUTER_SRC
    assert "month_bounds(" in ROUTER_SRC
    assert "validate_period(" in ROUTER_SRC


def test_router_404s_unknown_customer():
    assert '"Customer not found"' in ROUTER_SRC


def test_router_registered_in_main():
    assert "customer_statements.router" in MAIN_SRC
    assert "customer_statements," in MAIN_SRC
