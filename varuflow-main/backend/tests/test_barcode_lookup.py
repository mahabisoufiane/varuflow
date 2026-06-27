"""Tests for GET /api/inventory/products?barcode=… — scanner lookup.

The mobile scanner hits this endpoint with the raw EAN value. A match
should return the product as normal pagination; a miss should 404
distinctly so the app can show "Produkt hittades ej".
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.features.inventory.models import Product



async def _postgres_ok(db):
    try:
        await db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def test_barcode_lookup_returns_product(db_session, two_orgs, client_factory):
    if not await _postgres_ok(db_session):
        pytest.skip("PostgreSQL not reachable")
    org = two_orgs["a"]["org"]
    member = two_orgs["a"]["member"]

    p = Product(
        org_id=org.id, name="Scannable", sku="SCAN-1", unit="st",
        purchase_price=Decimal("10.00"), sell_price=Decimal("20.00"),
        tax_rate=Decimal("25.00"), is_active=True, barcode="7310865004703",
    )
    db_session.add(p)
    await db_session.commit()

    async with client_factory(member) as client:
        r = await client.get("/api/inventory/products?barcode=7310865004703")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["sku"] == "SCAN-1"


async def test_barcode_lookup_unknown_returns_404(db_session, two_orgs, client_factory):
    if not await _postgres_ok(db_session):
        pytest.skip("PostgreSQL not reachable")
    member = two_orgs["a"]["member"]

    async with client_factory(member) as client:
        r = await client.get("/api/inventory/products?barcode=0000000000000")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


async def test_barcode_lookup_isolated_per_org(db_session, two_orgs, client_factory):
    """A barcode registered in org B must not surface to org A."""
    if not await _postgres_ok(db_session):
        pytest.skip("PostgreSQL not reachable")
    org_b = two_orgs["b"]["org"]
    member_a = two_orgs["a"]["member"]

    p = Product(
        org_id=org_b.id, name="OrgB only", sku="B-1", unit="st",
        purchase_price=Decimal("10.00"), sell_price=Decimal("20.00"),
        tax_rate=Decimal("25.00"), is_active=True, barcode="1111111111111",
    )
    db_session.add(p)
    await db_session.commit()

    async with client_factory(member_a) as client:
        r = await client.get("/api/inventory/products?barcode=1111111111111")
    assert r.status_code == 404
