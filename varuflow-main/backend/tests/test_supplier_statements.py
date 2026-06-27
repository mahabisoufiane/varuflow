"""Item 93 — Supplier statements."""
from __future__ import annotations

import pathlib
from datetime import date
from decimal import Decimal

import pytest

from app.services import supplier_statement as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(p: str) -> str:
    _p = _BACKEND_ROOT / p
    if _p.is_file():
        return _p.read_text()
    # Path was split into a feature package (e.g. routers/invoicing/);
    # concatenate its modules so source-string assertions still hold.
    _pkg = _p.with_suffix("")
    if _pkg.is_dir():
        return "".join(_f.read_text() for _f in sorted(_pkg.rglob("*.py")))
    return _p.read_text()


SERVICE_SRC = _read("app/services/supplier_statement.py")
ROUTER_SRC  = _read("app/features/purchases/supplier_statements.py")
MAIN_SRC    = _read("app/main.py")


# ── validate_period ──────────────────────────────────────────────────────


def test_validate_period_ok():
    svc.validate_period(start=date(2026, 1, 1), end=date(2026, 1, 31))


def test_validate_period_reverse_rejected():
    with pytest.raises(ValueError):
        svc.validate_period(start=date(2026, 2, 1), end=date(2026, 1, 1))


def test_validate_period_too_long_rejected():
    with pytest.raises(ValueError):
        svc.validate_period(start=date(2024, 1, 1), end=date(2026, 1, 1))


def test_validate_period_rejects_non_date():
    with pytest.raises(ValueError):
        svc.validate_period(start="2026-01-01", end=date(2026, 1, 31))  # type: ignore[arg-type]


# ── month_bounds ─────────────────────────────────────────────────────────


def test_month_bounds_standard():
    assert svc.month_bounds(year=2026, month=4) == (
        date(2026, 4, 1), date(2026, 4, 30),
    )


def test_month_bounds_feb_leap():
    assert svc.month_bounds(year=2024, month=2) == (
        date(2024, 2, 1), date(2024, 2, 29),
    )


def test_month_bounds_feb_non_leap():
    assert svc.month_bounds(year=2026, month=2) == (
        date(2026, 2, 1), date(2026, 2, 28),
    )


def test_month_bounds_december():
    assert svc.month_bounds(year=2026, month=12) == (
        date(2026, 12, 1), date(2026, 12, 31),
    )


def test_month_bounds_bad_month():
    with pytest.raises(ValueError):
        svc.month_bounds(year=2026, month=13)
    with pytest.raises(ValueError):
        svc.month_bounds(year=2026, month=0)


def test_month_bounds_bad_year():
    with pytest.raises(ValueError):
        svc.month_bounds(year=1999, month=5)


# ── build_statement ──────────────────────────────────────────────────────


def _pv(
    id_: str, issue: date, total: Decimal | int,
    *, number: str | None = None,
    due: date | None = None,
    status: str = "DRAFT",
) -> svc.PayableRow:
    return svc.PayableRow(
        id=id_, number=number, issue_date=issue, due_date=due,
        total=Decimal(total), status=status,
    )


def _cr(
    id_: str, issue: date, total: Decimal | int,
    *, number: str | None = None,
    po: str | None = None,
    status: str = "ISSUED",
) -> svc.CreditRow:
    return svc.CreditRow(
        id=id_, number=number, purchase_order_id=po,
        issue_date=issue, total=Decimal(total), status=status,
    )


def test_build_empty_period():
    stmt = svc.build_statement(
        supplier_id="sup-1",
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
        payables=[],
        credits=[],
    )
    assert stmt.opening_balance == Decimal("0.00")
    assert stmt.closing_balance == Decimal("0.00")
    assert stmt.entries == []
    assert stmt.totals.outstanding == Decimal("0.00")


def test_build_opening_balance_from_prior_history():
    stmt = svc.build_statement(
        supplier_id="sup-1",
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
        payables=[_pv("pv-prev", date(2026, 3, 15), 500)],
        credits=[],
    )
    assert stmt.opening_balance == Decimal("500.00")
    assert stmt.closing_balance == Decimal("500.00")
    assert stmt.entries == []  # nothing happened in-window


def test_build_in_period_payable_increases_balance():
    stmt = svc.build_statement(
        supplier_id="sup-1",
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
        payables=[_pv("pv-1", date(2026, 4, 10), 200, number="SUP-001")],
        credits=[],
    )
    assert stmt.opening_balance == Decimal("0.00")
    assert stmt.closing_balance == Decimal("200.00")
    assert len(stmt.entries) == 1
    assert stmt.entries[0].kind == "payable"
    assert stmt.entries[0].balance == Decimal("200.00")
    assert stmt.totals.payables_issued == Decimal("200.00")


def test_build_issued_credit_reduces_balance():
    stmt = svc.build_statement(
        supplier_id="sup-1",
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
        payables=[_pv("pv-1", date(2026, 4, 5), 300)],
        credits=[_cr("cr-1", date(2026, 4, 20), 100, number="SCN-2026-0001")],
    )
    assert stmt.closing_balance == Decimal("200.00")
    kinds = [e.kind for e in stmt.entries]
    assert kinds == ["payable", "credit"]
    assert stmt.totals.credits_issued == Decimal("100.00")


def test_build_draft_and_voided_credits_ignored():
    stmt = svc.build_statement(
        supplier_id="sup-1",
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
        payables=[],
        credits=[
            _cr("cr-draft",  date(2026, 4, 10), 500, status="DRAFT"),
            _cr("cr-void",   date(2026, 4, 11), 500, status="VOIDED"),
            _cr("cr-ok",     date(2026, 4, 12), 100, status="ISSUED"),
        ],
    )
    assert stmt.totals.credits_issued == Decimal("100.00")
    # Only the ISSUED credit appears in the feed.
    assert [e.ref_id for e in stmt.entries] == ["cr-ok"]


def test_build_standalone_credit_still_reduces_balance():
    # Credit with no source PO still moves the overall balance.
    stmt = svc.build_statement(
        supplier_id="sup-1",
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
        payables=[_pv("pv-1", date(2026, 4, 5), 100)],
        credits=[_cr("cr-1", date(2026, 4, 10), 30, po=None)],
    )
    assert stmt.closing_balance == Decimal("70.00")


def test_build_same_day_payable_before_credit():
    # On the same day the balance must rise before it falls.
    stmt = svc.build_statement(
        supplier_id="sup-1",
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
        payables=[_pv("pv-1", date(2026, 4, 15), 100)],
        credits=[_cr("cr-1", date(2026, 4, 15), 40)],
    )
    assert [e.kind for e in stmt.entries] == ["payable", "credit"]
    assert stmt.entries[0].balance == Decimal("100.00")
    assert stmt.entries[1].balance == Decimal("60.00")


def test_build_totals_match_entries():
    stmt = svc.build_statement(
        supplier_id="sup-1",
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
        payables=[
            _pv("pv-1", date(2026, 4, 3), 100),
            _pv("pv-2", date(2026, 4, 10), 50),
        ],
        credits=[_cr("cr-1", date(2026, 4, 20), 30)],
    )
    assert stmt.totals.payables_issued == Decimal("150.00")
    assert stmt.totals.credits_issued == Decimal("30.00")
    assert stmt.totals.outstanding == Decimal("120.00")
    assert stmt.closing_balance == stmt.totals.outstanding


def test_build_chronological_ordering():
    stmt = svc.build_statement(
        supplier_id="sup-1",
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
        payables=[
            _pv("pv-b", date(2026, 4, 20), 20),
            _pv("pv-a", date(2026, 4, 5), 10),
        ],
        credits=[_cr("cr-mid", date(2026, 4, 15), 5)],
    )
    # date ordering wins across kinds
    dates = [e.entry_date for e in stmt.entries]
    assert dates == sorted(dates)


def test_build_per_payable_remaining_default_is_total():
    # The pure service doesn't allocate credits per payable (router
    # scope); every payable's ``remaining`` equals its ``total``.
    stmt = svc.build_statement(
        supplier_id="sup-1",
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
        payables=[_pv("pv-1", date(2026, 4, 5), 100)],
        credits=[_cr("cr-1", date(2026, 4, 10), 40, po="pv-1")],
    )
    p = stmt.payables[0]
    assert p.total == Decimal("100.00")
    assert p.credited == Decimal("0.00")
    assert p.remaining == Decimal("100.00")


def test_build_rejects_invalid_period():
    with pytest.raises(ValueError):
        svc.build_statement(
            supplier_id="sup-1",
            period_start=date(2026, 4, 30),
            period_end=date(2026, 4, 1),
            payables=[], credits=[],
        )


# ── Router source contract ───────────────────────────────────────────────


def test_router_prefix_and_endpoints():
    assert 'prefix="/api/supplier-statements"' in ROUTER_SRC
    assert '@router.get("/{supplier_id}", response_model=StatementOut)' in ROUTER_SRC
    assert '@router.get("/{supplier_id}/month", response_model=StatementOut)' in ROUTER_SRC


def test_router_tenant_scopes_all_queries():
    # Supplier lookup + payables + credits all filter by org_id.
    assert "Supplier.org_id == org_id" in ROUTER_SRC
    assert "PayableInvoice.org_id == org_id" in ROUTER_SRC
    assert "SupplierCreditNote.org_id == org_id" in ROUTER_SRC


def test_router_emits_single_audit_action():
    assert '"supplier_statement.viewed"' in ROUTER_SRC
    assert ROUTER_SRC.count('"supplier_statement.viewed"') == 2  # once per endpoint
    assert ROUTER_SRC.count("request=request") >= 2


def test_router_404_on_unknown_supplier():
    assert '"Supplier not found"' in ROUTER_SRC


def test_router_delegates_to_pure_service():
    assert "svc_93.build_statement" in ROUTER_SRC
    assert "svc_93.validate_period" in ROUTER_SRC
    assert "svc_93.month_bounds" in ROUTER_SRC


def test_router_filters_payables_without_issue_date():
    # Auto-draft payables with issue_date=None must not appear in a
    # statement (no date → no position on the ledger).
    assert "p.issue_date is not None" in ROUTER_SRC


def test_router_registered_in_main():

    # Registered via purchases_router (vertical-slice architecture).
    # The individual module is wired inside the feature router, not directly in main.py.
    feat_src = _read("app/features/purchases/router.py")
    assert "supplier_statements" in feat_src
    assert "purchases_router" in MAIN_SRC


# ── Service source contract ──────────────────────────────────────────────


def test_service_max_period_366():
    assert "MAX_PERIOD_DAYS: int = 366" in SERVICE_SRC


def test_service_balance_convention_documented():
    assert "positive = tenant owes the supplier" in SERVICE_SRC
