"""Item 69 — Bulk product import."""
from __future__ import annotations

import pathlib
from decimal import Decimal

import pytest

from app.services import product_import as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(p: str) -> str:
    return (_BACKEND_ROOT / p).read_text()


SERVICE_SRC = _read("app/services/product_import.py")
ROUTER_SRC = _read("app/routers/product_import.py")
MAIN_SRC = _read("app/main.py")


# ── Pure service: row validation ───────────────────────────────────────────


def _good_row(**overrides):
    base = {
        "sku": "A1",
        "name": "Widget",
        "purchase_price": "10.00",
        "sell_price": "15.00",
    }
    base.update(overrides)
    return base


def test_validate_row_minimum_fields_defaults():
    r = svc.validate_row(_good_row(), line=1)
    assert r.sku == "A1"
    assert r.name == "Widget"
    assert r.purchase_price == Decimal("10.00")
    assert r.sell_price == Decimal("15.00")
    assert r.category is None
    assert r.unit == "st"
    assert r.tax_rate == Decimal("25.00")
    assert r.barcode is None
    assert r.description is None
    assert r.reorder_level == 0


def test_validate_row_requires_sku():
    with pytest.raises(ValueError, match="sku is required"):
        svc.validate_row(_good_row(sku=""), line=1)


def test_validate_row_requires_name():
    with pytest.raises(ValueError, match="name is required"):
        svc.validate_row(_good_row(name="   "), line=1)


def test_validate_row_rejects_non_numeric_price():
    with pytest.raises(ValueError, match="purchase_price"):
        svc.validate_row(_good_row(purchase_price="abc"), line=1)


def test_validate_row_rejects_negative_sell_price():
    with pytest.raises(ValueError, match="sell_price"):
        svc.validate_row(_good_row(sell_price="-1"), line=1)


def test_validate_row_accepts_comma_decimal():
    r = svc.validate_row(_good_row(purchase_price="10,50"), line=1)
    assert r.purchase_price == Decimal("10.50")


def test_validate_row_rejects_invalid_tax_rate():
    with pytest.raises(ValueError, match="tax_rate"):
        svc.validate_row(_good_row(tax_rate="17"), line=1)


def test_validate_row_accepts_swedish_vat_rates():
    for rate in ("6", "12", "25"):
        r = svc.validate_row(_good_row(tax_rate=rate), line=1)
        assert r.tax_rate == Decimal(rate).quantize(Decimal("0.01"))


def test_validate_row_default_tax_rate_25():
    r = svc.validate_row(_good_row(tax_rate=""), line=1)
    assert r.tax_rate == Decimal("25.00")


def test_validate_row_reorder_level_integer():
    r = svc.validate_row(_good_row(reorder_level="7"), line=1)
    assert r.reorder_level == 7


def test_validate_row_reorder_level_rejects_negative():
    with pytest.raises(ValueError, match="reorder_level"):
        svc.validate_row(_good_row(reorder_level="-3"), line=1)


def test_validate_row_rejects_overlong_sku():
    long_sku = "X" * (svc.MAX_SKU_LENGTH + 1)
    with pytest.raises(ValueError, match="sku too long"):
        svc.validate_row(_good_row(sku=long_sku), line=1)


def test_validate_row_rejects_overlong_name():
    long_name = "Y" * (svc.MAX_NAME_LENGTH + 1)
    with pytest.raises(ValueError, match="name too long"):
        svc.validate_row(_good_row(name=long_name), line=1)


def test_validate_row_name_whitespace_collapsed():
    r = svc.validate_row(_good_row(name="  Widget   XL  "), line=1)
    assert r.name == "Widget XL"


def test_validate_row_optional_fields_preserved():
    r = svc.validate_row(
        _good_row(
            category="Tools", unit="kg", barcode="7310000000001",
            description="Premium", reorder_level="3",
        ),
        line=1,
    )
    assert r.category == "Tools"
    assert r.unit == "kg"
    assert r.barcode == "7310000000001"
    assert r.description == "Premium"
    assert r.reorder_level == 3


# ── Pure service: CSV parsing ──────────────────────────────────────────────


def test_parse_csv_rejects_empty_file():
    out = svc.parse_csv("")
    assert out.rows == []
    assert len(out.errors) == 1
    assert "empty" in out.errors[0].message


def test_parse_csv_rejects_missing_required_columns():
    out = svc.parse_csv("sku,name\nA1,Widget\n")
    assert out.rows == []
    assert any("missing required" in e.message for e in out.errors)


def test_parse_csv_happy_path_two_rows():
    csv_text = (
        "sku,name,purchase_price,sell_price,tax_rate\n"
        "A1,Widget,10,15,25\n"
        "B2,Gadget,5,9,12\n"
    )
    out = svc.parse_csv(csv_text)
    assert len(out.rows) == 2
    assert out.errors == []
    assert [r.sku for r in out.rows] == ["A1", "B2"]


def test_parse_csv_detects_duplicate_sku_in_file():
    csv_text = (
        "sku,name,purchase_price,sell_price\n"
        "A1,Widget,10,15\n"
        "A1,Gizmo,11,16\n"
    )
    out = svc.parse_csv(csv_text)
    assert len(out.rows) == 1
    assert any(
        e.field == "sku" and "duplicate" in e.message for e in out.errors
    )


def test_parse_csv_detects_duplicate_barcode_in_file():
    csv_text = (
        "sku,name,purchase_price,sell_price,barcode\n"
        "A1,Widget,10,15,7310000000001\n"
        "B2,Gadget,11,16,7310000000001\n"
    )
    out = svc.parse_csv(csv_text)
    assert len(out.rows) == 1
    assert any(e.field == "barcode" for e in out.errors)


def test_parse_csv_per_row_errors_dont_block_other_rows():
    csv_text = (
        "sku,name,purchase_price,sell_price\n"
        "A1,Widget,10,15\n"
        ",Gadget,5,9\n"        # missing sku
        "B2,Gizmo,-1,9\n"      # negative price
        "B3,Good,4,8\n"
    )
    out = svc.parse_csv(csv_text)
    assert [r.sku for r in out.rows] == ["A1", "B3"]
    assert len(out.errors) == 2
    assert {e.line for e in out.errors} == {2, 3}


def test_parse_csv_ignores_unknown_columns():
    csv_text = (
        "sku,name,purchase_price,sell_price,vendor_notes\n"
        "A1,Widget,10,15,delivered fast\n"
    )
    out = svc.parse_csv(csv_text)
    assert len(out.rows) == 1


def test_parse_csv_header_case_insensitive():
    csv_text = (
        "SKU,NAME,Purchase_Price,Sell_Price\n"
        "A1,Widget,10,15\n"
    )
    out = svc.parse_csv(csv_text)
    assert len(out.rows) == 1
    assert out.rows[0].sku == "A1"


def test_parse_csv_caps_row_count():
    header = "sku,name,purchase_price,sell_price\n"
    body = "\n".join(
        f"S{i},Widget,1,2" for i in range(svc.MAX_ROWS + 5)
    )
    out = svc.parse_csv(header + body + "\n")
    assert any("exceeds" in e.message for e in out.errors)
    assert len(out.rows) <= svc.MAX_ROWS


def test_parse_csv_non_string_raises():
    with pytest.raises(ValueError):
        svc.parse_csv(b"sku,name")  # type: ignore[arg-type]


# ── Pure service: classify against existing ───────────────────────────────


def test_classify_splits_inserts_and_updates():
    rows = [
        svc.validate_row(_good_row(sku="A1"), line=1),
        svc.validate_row(_good_row(sku="B2"), line=2),
        svc.validate_row(_good_row(sku="C3"), line=3),
    ]
    inserts, updates = svc.classify_against_existing(
        rows, existing_skus={"B2"}
    )
    assert [r.sku for r in inserts] == ["A1", "C3"]
    assert [r.sku for r in updates] == ["B2"]


# ── Router source contract ────────────────────────────────────────────────


def test_router_has_bulk_import_endpoint():
    assert "/products/bulk-import" in ROUTER_SRC
    assert 'prefix="/api/inventory"' in ROUTER_SRC


def test_router_restricted_to_owner_admin():
    assert "OrgRole.OWNER" in ROUTER_SRC
    assert "OrgRole.ADMIN" in ROUTER_SRC
    assert "403" in ROUTER_SRC


def test_router_logs_bulk_imported_action():
    assert '"product.bulk_imported"' in ROUTER_SRC
    assert "request=request" in ROUTER_SRC


def test_router_tenant_scopes_sku_lookup():
    # SKU lookup must filter by org_id to avoid cross-tenant leakage.
    assert "Product.org_id == member.org_id" in ROUTER_SRC
    assert "Product.sku.in_" in ROUTER_SRC


def test_router_locks_org_row_before_mutation():
    assert "with_for_update" in ROUTER_SRC
    assert "Organization.id == member.org_id" in ROUTER_SRC


def test_router_registered_in_main():
    assert "product_import.router" in MAIN_SRC
    assert "import product_import" in MAIN_SRC or "product_import," in MAIN_SRC
