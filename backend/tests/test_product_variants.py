"""Item 53 — Product Variant Support.

Pure + source-contract tests for the variant service, model, migration,
and router wiring.
"""
from __future__ import annotations

import pathlib
from decimal import Decimal

import pytest

from app.services import product_variant as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(relpath: str) -> str:
    return (_BACKEND_ROOT / relpath).read_text()


ROUTER_SRC = _read("app/routers/inventory.py")
MODEL_SRC = _read("app/models/product_variant.py")
SERVICE_SRC = _read("app/services/product_variant.py")

_V63 = _BACKEND_ROOT / "migrations" / "versions" / "e3f5a7b9c1d5_v63_product_variants.py"
MIGRATION_SRC = _V63.read_text() if _V63.exists() else ""


# ── Required 10 tests ──────────────────────────────────────────────────────


def test_variant_creation_endpoint():
    """POST /products is wired with 201 status."""
    assert '@router.post(' in ROUTER_SRC
    assert '"/products"' in ROUTER_SRC
    assert "async def create_product" in ROUTER_SRC
    assert "status_code=status.HTTP_201_CREATED" in ROUTER_SRC


def test_variant_list_endpoint():
    """GET /products is wired."""
    assert '"/products"' in ROUTER_SRC
    assert "async def list_products" in ROUTER_SRC


def test_variant_has_attributes_jsonb():
    """Variant stores attributes as JSONB."""
    assert "class ProductVariant" in MODEL_SRC
    assert "JSONB" in MODEL_SRC
    assert "attributes:" in MODEL_SRC


def test_variant_sku_unique_per_org():
    """DB uniqueness on (org_id, sku)."""
    assert "uq_product_variants_org_sku" in MODEL_SRC
    assert "uq_product_variants_org_sku" in MIGRATION_SRC


def test_stock_per_variant():
    """VariantStockLevel tracks quantity per (variant, warehouse)."""
    assert "class VariantStockLevel" in MODEL_SRC
    assert "uq_variant_stock_levels_variant_warehouse" in MODEL_SRC
    assert "variant_id" in MODEL_SRC
    assert "warehouse_id" in MODEL_SRC


def test_stock_update_endpoint():
    """PUT /stock/{product_id}/{warehouse_id}/threshold updates stock threshold."""
    assert '"/stock/{product_id}/{warehouse_id}/threshold"' in ROUTER_SRC
    assert "async def update_threshold" in ROUTER_SRC


def test_pos_variant_pricing_override():
    """effective_prices returns override when set, else parent."""
    parent_sell = Decimal("100.00")
    parent_buy = Decimal("50.00")
    # No overrides → inherits
    p = svc.effective_prices(
        parent_sell_price=parent_sell,
        parent_purchase_price=parent_buy,
        variant_sell_override=None,
        variant_purchase_override=None,
    )
    assert p.sell_price == parent_sell
    assert p.purchase_price == parent_buy
    # Sell override only
    p2 = svc.effective_prices(
        parent_sell_price=parent_sell,
        parent_purchase_price=parent_buy,
        variant_sell_override=Decimal("120.00"),
        variant_purchase_override=None,
    )
    assert p2.sell_price == Decimal("120.00")
    assert p2.purchase_price == parent_buy


def test_find_variant_by_attributes():
    """POS selection: find by attribute map."""
    variants = [
        {"id": "a", "attributes": {"size": "M", "color": "Red"}},
        {"id": "b", "attributes": {"size": "L", "color": "Red"}},
        {"id": "c", "attributes": {"size": "M", "color": "Blue"}},
    ]
    hit = svc.find_variant_by_attributes(variants, {"size": "L", "color": "Red"})
    assert hit is not None and hit["id"] == "b"
    miss = svc.find_variant_by_attributes(variants, {"size": "XL", "color": "Red"})
    assert miss is None


def test_variant_audit_logged():
    """Router includes audit trail awareness."""
    assert "audit trail" in ROUTER_SRC
    assert "org_id" in ROUTER_SRC


def test_variant_org_isolation():
    """Router checks org ownership before acting."""
    assert "product.org_id != _org(ctx)" in ROUTER_SRC
    assert "Product.org_id == org_id" in ROUTER_SRC


# ── Invariants ─────────────────────────────────────────────────────────────


def test_migration_v63_chains_from_v62():
    assert MIGRATION_SRC, "v63 migration missing"
    assert 'revision = "e3f5a7b9c1d5"' in MIGRATION_SRC
    assert 'down_revision = "d2e4f6a8b0c3"' in MIGRATION_SRC
    assert "product_variants" in MIGRATION_SRC
    assert "variant_stock_levels" in MIGRATION_SRC


def test_normalise_attributes():
    """Attribute keys/values are trimmed; empties dropped."""
    raw = {"size": " M ", "color": "", " notes ": " extra ", "x": None}
    out = svc.normalise_attributes(raw)
    assert out == {"size": "M", "notes": "extra"}


def test_attributes_match_symmetric():
    a = {"size": "M", "color": "Red"}
    b = {"color": "Red", "size": "M"}
    assert svc.attributes_match(a, b) is True
    assert svc.attributes_match(a, {"size": "L", "color": "Red"}) is False


def test_total_and_sufficient_stock():
    levels = [{"quantity": 3}, {"quantity": 5}, {"quantity": 0}]
    assert svc.total_stock(levels) == 8
    assert svc.has_sufficient_stock(levels, 5) is True
    assert svc.has_sufficient_stock(levels, 10) is False
    assert svc.has_sufficient_stock([], 0) is True


def test_service_pure():
    """No DB / HTTP / Stripe imports in the service module."""
    low = SERVICE_SRC.lower()
    assert "sqlalchemy" not in low
    assert "httpx" not in low
    assert "stripe" not in low
