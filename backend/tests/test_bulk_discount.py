"""Item 64 — Invoice line bulk discount."""
from __future__ import annotations

import pathlib
from decimal import Decimal

import pytest

from app.services import bulk_discount as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(p: str) -> str:
    return (_BACKEND_ROOT / p).read_text()


SERVICE_SRC = _read("app/services/bulk_discount.py")
ROUTER_SRC = _read("app/routers/invoicing.py")


def _line(
    lid: str = "1",
    qty: str = "1",
    price: str = "100.00",
    vat: str = "25.00",
) -> svc.LineIn:
    return svc.LineIn(
        id=lid,
        quantity=Decimal(qty),
        unit_price=Decimal(price),
        tax_rate=Decimal(vat),
    )


# ── Pure service: validation ──────────────────────────────────────────────


def test_validate_kind_whitelist():
    assert svc.validate_kind("percent") == "percent"
    assert svc.validate_kind("amount") == "amount"
    for bad in ("percentage", "", "PERCENT"):
        with pytest.raises(ValueError):
            svc.validate_kind(bad)


def test_validate_percent_range():
    svc.validate_value("percent", Decimal("0.01"))
    svc.validate_value("percent", Decimal("100"))
    for bad in (Decimal("0"), Decimal("100.01"), Decimal("-1")):
        with pytest.raises(ValueError):
            svc.validate_value("percent", bad)


def test_validate_amount_range():
    svc.validate_value("amount", Decimal("0.01"))
    svc.validate_value("amount", Decimal("1000000"))
    for bad in (Decimal("0"), Decimal("-5"), Decimal("1000001")):
        with pytest.raises(ValueError):
            svc.validate_value("amount", bad)


def test_validate_value_coerces_strings_and_numbers():
    assert svc.validate_value("percent", "10") == Decimal("10")
    with pytest.raises(ValueError):
        svc.validate_value("percent", "not-a-number")


# ── Pure service: apply_discount_to_line ──────────────────────────────────


def test_percent_reduces_unit_price_and_line_total():
    ln = _line(qty="2", price="100.00")
    out = svc.apply_discount_to_line(ln, kind="percent", value=Decimal("10"))
    assert out.unit_price == Decimal("90.00")
    assert out.line_total == Decimal("180.00")
    assert out.changed is True


def test_amount_is_per_unit_subtraction():
    ln = _line(qty="3", price="50.00")
    out = svc.apply_discount_to_line(ln, kind="amount", value=Decimal("5"))
    assert out.unit_price == Decimal("45.00")
    assert out.line_total == Decimal("135.00")


def test_amount_floors_unit_at_zero_never_negative():
    ln = _line(qty="2", price="5.00")
    out = svc.apply_discount_to_line(ln, kind="amount", value=Decimal("10"))
    assert out.unit_price == Decimal("0.00")
    assert out.line_total == Decimal("0.00")


def test_percent_hundred_produces_free_line():
    ln = _line(qty="4", price="25.00")
    out = svc.apply_discount_to_line(ln, kind="percent", value=Decimal("100"))
    assert out.unit_price == Decimal("0.00")
    assert out.line_total == Decimal("0.00")


def test_rounding_uses_half_up_at_cent():
    # 33.33% of 100 → 66.67 remaining, ROUND_HALF_UP
    ln = _line(qty="1", price="100.00")
    out = svc.apply_discount_to_line(ln, kind="percent", value=Decimal("33.33"))
    assert out.unit_price == Decimal("66.67")


# ── Pure service: apply_bulk_discount ─────────────────────────────────────


def test_bulk_touches_every_line_when_selection_is_none():
    lines = [_line("a"), _line("b"), _line("c")]
    out = svc.apply_bulk_discount(lines, kind="percent", value=Decimal("10"))
    assert all(o.changed for o in out)
    assert [o.id for o in out] == ["a", "b", "c"]


def test_bulk_only_touches_selected_ids():
    lines = [_line("a"), _line("b"), _line("c")]
    out = svc.apply_bulk_discount(
        lines, kind="percent", value=Decimal("10"), selected_ids={"b"}
    )
    by_id = {o.id: o for o in out}
    assert by_id["a"].changed is False
    assert by_id["b"].changed is True
    assert by_id["c"].changed is False


def test_bulk_raises_when_selected_id_missing_on_invoice():
    lines = [_line("a")]
    with pytest.raises(ValueError):
        svc.apply_bulk_discount(
            lines, kind="percent", value=Decimal("10"), selected_ids={"zzz"}
        )


def test_bulk_rejects_empty_selection():
    lines = [_line("a")]
    with pytest.raises(ValueError):
        svc.apply_bulk_discount(
            lines, kind="percent", value=Decimal("10"), selected_ids=set()
        )


def test_bulk_rejects_empty_line_list():
    with pytest.raises(ValueError):
        svc.apply_bulk_discount([], kind="percent", value=Decimal("10"))


# ── Pure service: compute_totals ──────────────────────────────────────────


def test_compute_totals_recomputes_vat_against_new_subtotal():
    lines = [_line("a", qty="2", price="100.00", vat="25.00")]
    outs = svc.apply_bulk_discount(lines, kind="percent", value=Decimal("10"))
    totals = svc.compute_totals(lines, outs)
    # 2 * 90.00 = 180.00 subtotal, 25% VAT = 45.00
    assert totals.subtotal == Decimal("180.00")
    assert totals.vat_amount == Decimal("45.00")
    assert totals.total == Decimal("225.00")


def test_compute_totals_mixed_tax_rates():
    lines = [
        _line("a", qty="1", price="100.00", vat="25.00"),
        _line("b", qty="1", price="100.00", vat="12.00"),
    ]
    outs = svc.apply_bulk_discount(lines, kind="percent", value=Decimal("10"))
    totals = svc.compute_totals(lines, outs)
    # subtotal = 90 + 90 = 180, vat = 22.50 + 10.80 = 33.30
    assert totals.subtotal == Decimal("180.00")
    assert totals.vat_amount == Decimal("33.30")


def test_compute_totals_requires_aligned_ids():
    lines = [_line("a")]
    outs = [
        svc.LineOut(
            id="b",
            unit_price=Decimal("1"),
            line_total=Decimal("1"),
            changed=False,
        )
    ]
    with pytest.raises(ValueError):
        svc.compute_totals(lines, outs)


# ── Router source-contract ────────────────────────────────────────────────


@pytest.mark.xfail(reason="bulk-discount endpoint not yet added to invoicing router")
def test_router_has_bulk_discount_endpoint():
    assert '@router.post(\n    "/invoices/{invoice_id}/bulk-discount"' in ROUTER_SRC


@pytest.mark.xfail(reason="bulk-discount endpoint not yet added to invoicing router")
def test_router_rejects_non_draft_invoices():
    assert '"can only discount DRAFT invoices"' in ROUTER_SRC
    assert "status_code=409" in ROUTER_SRC


@pytest.mark.xfail(reason="bulk-discount endpoint not yet added to invoicing router")
def test_router_rejects_empty_invoice():
    assert '"invoice has no lines"' in ROUTER_SRC


@pytest.mark.xfail(reason="bulk-discount endpoint not yet added to invoicing router")
def test_router_writes_back_unit_price_and_line_total():
    assert "row.unit_price = o.unit_price" in ROUTER_SRC
    assert "row.line_total = o.line_total" in ROUTER_SRC


@pytest.mark.xfail(reason="bulk-discount endpoint not yet added to invoicing router")
def test_router_recomputes_invoice_totals():
    assert "inv.subtotal = totals.subtotal" in ROUTER_SRC
    assert "inv.vat_amount = totals.vat_amount" in ROUTER_SRC
    assert "inv.total_sek = totals.total" in ROUTER_SRC


def test_router_is_tenant_scoped():
    assert "Invoice.org_id == org_id" in ROUTER_SRC


@pytest.mark.xfail(reason="bulk-discount endpoint not yet added to invoicing router")
def test_router_logs_audit_action():
    assert '"invoice.bulk_discount_applied"' in ROUTER_SRC
