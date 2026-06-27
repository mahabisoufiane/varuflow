"""Tests for Supplier Lead Time Tracker (v19)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.features.inventory.models import (
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    StockLevel,
    Supplier,
    Warehouse,
)
from app.features.auth.organization import OrgPlan
from app.features.purchases.supplier_lead_time import SupplierLeadTime




async def _seed_supplier(db, org_id, *, default_lead_days: int | None = None, name="Acme AB"):
    s = Supplier(org_id=org_id, name=name, default_lead_days=default_lead_days)
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


async def _seed_po(
    db, org_id, supplier_id, *, ordered_days_ago: int,
    product_id: uuid.UUID, qty: int = 1, price: Decimal = Decimal("10.00"),
) -> PurchaseOrder:
    po = PurchaseOrder(
        org_id=org_id,
        supplier_id=supplier_id,
        status=PurchaseOrderStatus.SENT,
        total=price * qty,
    )
    db.add(po)
    await db.flush()
    # Back-date created_at so the capture math reads a non-zero lead time.
    po.created_at = datetime.now(timezone.utc) - timedelta(days=ordered_days_ago)
    db.add(PurchaseOrderItem(
        purchase_order_id=po.id,
        product_id=product_id,
        quantity=qty,
        unit_price=price,
        line_total=price * qty,
    ))
    await db.commit()
    await db.refresh(po)
    return po


async def _seed_product_and_warehouse(db, org_id):
    wh = Warehouse(org_id=org_id, name="LT-WH")
    db.add(wh)
    p = Product(
        org_id=org_id,
        name="Grej",
        sku=f"LT-{uuid.uuid4().hex[:6]}",
        unit="st",
        purchase_price=Decimal("10.00"),
        sell_price=Decimal("20.00"),
    )
    db.add(p)
    await db.flush()
    db.add(StockLevel(org_id=org_id, product_id=p.id, warehouse_id=wh.id, quantity=0))
    await db.commit()
    await db.refresh(p)
    return p, wh


async def test_receive_po_captures_lead_time(db_session, two_orgs, client_factory):
    org = two_orgs["a"]["org"]
    await db_session.commit()

    supplier = await _seed_supplier(db_session, org.id, default_lead_days=5)
    product, _wh = await _seed_product_and_warehouse(db_session, org.id)
    po = await _seed_po(
        db_session, org.id, supplier.id,
        ordered_days_ago=7, product_id=product.id,
    )

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.patch(
            f"/api/inventory/purchase-orders/{po.id}/status",
            json={"status": "RECEIVED"},
        )
    assert r.status_code == 200, r.text

    # One supplier_lead_times row should exist with lead_days == 7
    row = (
        await db_session.execute(
            SupplierLeadTime.__table__.select().where(
                SupplierLeadTime.purchase_order_id == po.id,
            )
        )
    ).first()
    assert row is not None
    assert row.lead_days == 7
    assert row.supplier_id == supplier.id

    # Supplier's rolling average should be refreshed.
    await db_session.refresh(supplier)
    assert supplier.average_lead_days is not None
    assert float(supplier.average_lead_days) == pytest.approx(7.0, abs=0.1)
    assert supplier.last_lead_measured_at is not None


async def test_lead_time_endpoint_returns_stats(db_session, two_orgs, client_factory):
    org = two_orgs["a"]["org"]
    await db_session.commit()

    supplier = await _seed_supplier(db_session, org.id, default_lead_days=5, name="StatsCo")

    # Seed three historical rows: 4, 6, 10 days.
    for days in (4, 6, 10):
        db_session.add(SupplierLeadTime(
            org_id=org.id,
            supplier_id=supplier.id,
            purchase_order_id=uuid.uuid4(),
            ordered_at=datetime.now(timezone.utc) - timedelta(days=days + 1),
            received_at=datetime.now(timezone.utc) - timedelta(days=1),
            lead_days=days,
        ))
    await db_session.commit()

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get(f"/api/inventory/suppliers/{supplier.id}/lead-time")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["supplier_id"] == str(supplier.id)
    assert body["default_lead_days"] == 5
    assert body["sample_size"] == 3
    # Average of 4, 6, 10 = 6.667
    assert 6.5 <= body["average_lead_days"] <= 6.8
    # p90 of [4, 6, 10] via linear interpolation ≈ 9.2
    assert body["p90_lead_days"] >= 8.0
    assert len(body["recent"]) == 3


async def test_lead_time_endpoint_empty_supplier(db_session, two_orgs, client_factory):
    org = two_orgs["a"]["org"]
    await db_session.commit()
    supplier = await _seed_supplier(db_session, org.id, name="NewSup")

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get(f"/api/inventory/suppliers/{supplier.id}/lead-time")
    assert r.status_code == 200
    body = r.json()
    assert body["sample_size"] == 0
    assert body["average_lead_days"] == 0.0
    assert body["recent"] == []


async def test_lead_time_cross_org_404(db_session, two_orgs, client_factory):
    """Supplier belonging to org B cannot be read by org A."""
    org_b = two_orgs["b"]["org"]
    await db_session.commit()
    supplier_b = await _seed_supplier(db_session, org_b.id, name="SupplierB")

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get(f"/api/inventory/suppliers/{supplier_b.id}/lead-time")
    assert r.status_code == 404


async def test_slow_supplier_ai_card_fires_above_threshold(
    db_session, two_orgs, client_factory
):
    """Average lead > 1.5× default with ≥3 samples should surface a card."""
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()

    supplier = await _seed_supplier(db_session, org.id, default_lead_days=5, name="SlowCo")
    # Seed 3 lead-time rows averaging 12 days (> 5 * 1.5 = 7.5).
    for days in (10, 12, 14):
        db_session.add(SupplierLeadTime(
            org_id=org.id,
            supplier_id=supplier.id,
            purchase_order_id=uuid.uuid4(),
            ordered_at=datetime.now(timezone.utc) - timedelta(days=days + 1),
            received_at=datetime.now(timezone.utc) - timedelta(days=1),
            lead_days=days,
        ))
    supplier.average_lead_days = Decimal("12.0")
    await db_session.commit()

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/ai/cards")
    assert r.status_code == 200

    cards = r.json()["cards"]
    slow = next(
        (c for c in cards if (c.get("meta") or {}).get("kind") == "slow_supplier"),
        None,
    )
    assert slow is not None
    assert slow["meta"]["supplier_id"] == str(supplier.id)
    assert slow["meta"]["default_lead_days"] == 5
    assert slow["meta"]["sample_size"] == 3


async def test_slow_supplier_suppressed_when_sample_size_below_3(
    db_session, two_orgs, client_factory
):
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()

    supplier = await _seed_supplier(db_session, org.id, default_lead_days=5, name="TooNew")
    # Only 2 samples — below threshold even though avg is egregious.
    for days in (20, 22):
        db_session.add(SupplierLeadTime(
            org_id=org.id,
            supplier_id=supplier.id,
            purchase_order_id=uuid.uuid4(),
            ordered_at=datetime.now(timezone.utc) - timedelta(days=days + 1),
            received_at=datetime.now(timezone.utc) - timedelta(days=1),
            lead_days=days,
        ))
    supplier.average_lead_days = Decimal("21.0")
    await db_session.commit()

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/ai/cards")
    assert r.status_code == 200
    cards = r.json()["cards"]
    assert not any(
        (c.get("meta") or {}).get("kind") == "slow_supplier"
        and c["meta"].get("supplier_id") == str(supplier.id)
        for c in cards
    )


async def test_slow_supplier_not_fired_when_within_tolerance(
    db_session, two_orgs, client_factory
):
    """Observed average within 1.5× default should NOT fire the card."""
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()

    supplier = await _seed_supplier(db_session, org.id, default_lead_days=5, name="OnTimeCo")
    for days in (5, 6, 7):
        db_session.add(SupplierLeadTime(
            org_id=org.id,
            supplier_id=supplier.id,
            purchase_order_id=uuid.uuid4(),
            ordered_at=datetime.now(timezone.utc) - timedelta(days=days + 1),
            received_at=datetime.now(timezone.utc) - timedelta(days=1),
            lead_days=days,
        ))
    supplier.average_lead_days = Decimal("6.0")
    await db_session.commit()

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/ai/cards")
    assert r.status_code == 200
    cards = r.json()["cards"]
    assert not any(
        (c.get("meta") or {}).get("kind") == "slow_supplier"
        and c["meta"].get("supplier_id") == str(supplier.id)
        for c in cards
    )
