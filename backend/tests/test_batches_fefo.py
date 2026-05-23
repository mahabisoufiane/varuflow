"""Feature 21 — Batch + expiry tracking + FEFO tests.

Verifies:
- POST /api/inventory/batches registers a batch and bumps StockLevel.
- OUT /api/inventory/movements without a batch_id picks the
  oldest-expiry batch first (FEFO) and decrements only that lot.
- An explicit batch_id overrides FEFO and decrements the chosen lot.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import (
    Product,
    ProductBatch,
    StockLevel,
    StockMovement,
    StockMovementType,
    Warehouse,
)


@pytest_asyncio.fixture
async def warehouse_and_product(db_session: AsyncSession, two_orgs):
    org = two_orgs["a"]["org"]
    wh = Warehouse(id=uuid.uuid4(), org_id=org.id, name="Main")
    prod = Product(
        id=uuid.uuid4(), org_id=org.id, name="Yoghurt Naturell",
        sku="SKU-YOG", purchase_price=Decimal("8"),
        sell_price=Decimal("15"), reorder_level=10, is_active=True,
    )
    db_session.add_all([wh, prod])
    await db_session.commit()
    return {
        "org": org, "member": two_orgs["a"]["member"],
        "warehouse": wh, "product": prod,
    }


async def _post_batch(client, product, warehouse, *, batch_number, expiry, qty):
    res = await client.post("/api/inventory/batches", json={
        "product_id": str(product.id),
        "warehouse_id": str(warehouse.id),
        "batch_number": batch_number,
        "expiry_date": expiry.isoformat(),
        "quantity": qty,
    })
    assert res.status_code == 201, res.text
    return res.json()


@pytest.mark.asyncio
async def test_fefo_picks_oldest_expiry_first(
    db_session: AsyncSession, warehouse_and_product, client_factory,
):
    wp = warehouse_and_product
    product = wp["product"]
    warehouse = wp["warehouse"]

    async with client_factory(wp["member"]) as client:
        # Seed three batches out of expiry order. FEFO must pick B-MID
        # (expiry 2026-05-10) first because it is the oldest among the
        # three even though it was registered last.
        b_late = await _post_batch(
            client, product, warehouse,
            batch_number="B-LATE",
            expiry=date(2026, 8, 1), qty=10,
        )
        b_early = await _post_batch(
            client, product, warehouse,
            batch_number="B-EARLY",
            expiry=date(2026, 6, 1), qty=10,
        )
        b_mid = await _post_batch(
            client, product, warehouse,
            batch_number="B-MID",
            expiry=date(2026, 5, 10), qty=10,
        )

        # StockLevel should total 30 across the three batches.
        sl = await db_session.scalar(
            select(StockLevel).where(
                StockLevel.product_id == product.id,
                StockLevel.warehouse_id == warehouse.id,
            )
        )
        await db_session.refresh(sl)
        assert sl.quantity == 30

        # OUT of 4 units without batch_id → picks B-MID (oldest expiry).
        res = await client.post("/api/inventory/movements", json={
            "product_id": str(product.id),
            "warehouse_id": str(warehouse.id),
            "type": "OUT",
            "quantity": 4,
        })
        assert res.status_code == 201, res.text
        payload = res.json()
        assert payload["batch_id"] == b_mid["id"]

        # B-MID now 6, others untouched.
        mid = await db_session.get(ProductBatch, uuid.UUID(b_mid["id"]))
        early = await db_session.get(ProductBatch, uuid.UUID(b_early["id"]))
        late = await db_session.get(ProductBatch, uuid.UUID(b_late["id"]))
        await db_session.refresh(mid)
        await db_session.refresh(early)
        await db_session.refresh(late)
        assert mid.quantity == 6
        assert early.quantity == 10
        assert late.quantity == 10

        # Explicit batch_id overrides FEFO — force-pick B-LATE.
        res = await client.post("/api/inventory/movements", json={
            "product_id": str(product.id),
            "warehouse_id": str(warehouse.id),
            "type": "OUT",
            "quantity": 3,
            "batch_id": b_late["id"],
        })
        assert res.status_code == 201, res.text
        assert res.json()["batch_id"] == b_late["id"]
        await db_session.refresh(late)
        assert late.quantity == 7

        # Movement audit trail: the FEFO pick was recorded with batch_id
        # set on the StockMovement row so the warehouse slip reflects
        # which lot physically left the shelf.
        movements = (await db_session.execute(
            select(StockMovement)
            .where(
                StockMovement.product_id == product.id,
                StockMovement.type == StockMovementType.OUT,
            )
            .order_by(StockMovement.created_at.asc())
        )).scalars().all()
        assert len(movements) == 2
        assert str(movements[0].batch_id) == b_mid["id"]
        assert str(movements[1].batch_id) == b_late["id"]


@pytest.mark.asyncio
async def test_list_batches_filters_by_product_and_orders_fefo(
    db_session: AsyncSession, warehouse_and_product, client_factory,
):
    wp = warehouse_and_product
    product = wp["product"]
    warehouse = wp["warehouse"]

    async with client_factory(wp["member"]) as client:
        await _post_batch(
            client, product, warehouse,
            batch_number="A", expiry=date(2027, 1, 1), qty=5,
        )
        await _post_batch(
            client, product, warehouse,
            batch_number="B", expiry=date(2026, 7, 1), qty=5,
        )

        res = await client.get(
            "/api/inventory/batches",
            params={"product_id": str(product.id)},
        )
        assert res.status_code == 200
        rows = res.json()
        assert [r["batch_number"] for r in rows] == ["B", "A"]
