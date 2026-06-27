"""Item 14 — Stock count backend tests."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.compliance.audit_models import AuditLogEntry
from app.features.inventory.models import (
    Product,
    StockLevel,
    StockMovement,
    StockMovementType,
    Warehouse,
)
from app.features.inventory.stock_count import StockCount, StockCountItem, StockCountStatus


@pytest_asyncio.fixture
async def warehouse_and_products(db_session: AsyncSession, two_orgs):
    org = two_orgs["a"]["org"]
    wh = Warehouse(id=uuid.uuid4(), org_id=org.id, name="Main")
    p1 = Product(
        id=uuid.uuid4(), org_id=org.id, name="Widget", sku="SKU-W1",
        purchase_price=Decimal("10"), sell_price=Decimal("20"),
        reorder_level=5, is_active=True,
    )
    p2 = Product(
        id=uuid.uuid4(), org_id=org.id, name="Gadget", sku="SKU-G1",
        purchase_price=Decimal("5"), sell_price=Decimal("9"),
        reorder_level=3, is_active=True,
    )
    sl1 = StockLevel(
        id=uuid.uuid4(), org_id=org.id, product_id=p1.id,
        warehouse_id=wh.id, quantity=10,
    )
    sl2 = StockLevel(
        id=uuid.uuid4(), org_id=org.id, product_id=p2.id,
        warehouse_id=wh.id, quantity=4,
    )
    db_session.add_all([wh, p1, p2, sl1, sl2])
    await db_session.commit()
    return {
        "org": org,
        "member": two_orgs["a"]["member"],
        "warehouse": wh,
        "p1": p1,
        "p2": p2,
    }


@pytest.mark.asyncio
async def test_create_stock_count_draft(
    db_session: AsyncSession, warehouse_and_products, client_factory,
):
    ctx = warehouse_and_products
    async with client_factory(ctx["member"]) as client:
        res = await client.post("/api/stock-counts", json={
            "warehouse_id": str(ctx["warehouse"].id),
            "items": [
                {"product_id": str(ctx["p1"].id), "expected_qty": 10, "counted_qty": 10},
                {"product_id": str(ctx["p2"].id), "expected_qty": 4, "counted_qty": 2},
            ],
        })
        assert res.status_code == 201, res.text
        payload = res.json()
        assert payload["status"] == "DRAFT"
        assert len(payload["items"]) == 2


@pytest.mark.asyncio
async def test_submit_stock_count(
    db_session: AsyncSession, warehouse_and_products, client_factory,
):
    ctx = warehouse_and_products
    async with client_factory(ctx["member"]) as client:
        r1 = await client.post("/api/stock-counts", json={
            "warehouse_id": str(ctx["warehouse"].id),
            "items": [
                {"product_id": str(ctx["p1"].id), "counted_qty": 12},
            ],
        })
        cid = r1.json()["id"]
        r2 = await client.post(f"/api/stock-counts/{cid}/submit")
        assert r2.status_code == 200, r2.text
        assert r2.json()["status"] == "SUBMITTED"
        # Expected was refreshed from StockLevel (10).
        item = r2.json()["items"][0]
        assert item["expected_qty"] == 10
        assert item["counted_qty"] == 12
        assert item["variance_qty"] == 2


@pytest.mark.asyncio
async def test_stock_count_variance_adjustments(
    db_session: AsyncSession, warehouse_and_products, client_factory,
):
    ctx = warehouse_and_products
    async with client_factory(ctx["member"]) as client:
        r1 = await client.post("/api/stock-counts", json={
            "warehouse_id": str(ctx["warehouse"].id),
            "items": [
                {"product_id": str(ctx["p1"].id), "counted_qty": 7},   # variance -3
                {"product_id": str(ctx["p2"].id), "counted_qty": 4},   # match
            ],
        })
        cid = r1.json()["id"]
        await client.post(f"/api/stock-counts/{cid}/submit")
        r3 = await client.post(f"/api/stock-counts/{cid}/sync")
        assert r3.status_code == 200, r3.text
        summary = r3.json()
        assert summary["adjustments"] == 1
        assert summary["matches"] == 1
        assert summary["negative"] == 1

    # Stock level for p1 must now be 7.
    sl1 = await db_session.scalar(
        select(StockLevel).where(
            StockLevel.product_id == ctx["p1"].id,
            StockLevel.warehouse_id == ctx["warehouse"].id,
        )
    )
    await db_session.refresh(sl1)
    assert sl1.quantity == 7

    # A single ADJUSTMENT movement exists with reason "Stock count adjustment".
    mv = await db_session.scalar(
        select(StockMovement).where(
            StockMovement.product_id == ctx["p1"].id,
            StockMovement.type == StockMovementType.ADJUSTMENT,
        )
    )
    assert mv is not None
    assert mv.note == "Stock count adjustment"


@pytest.mark.asyncio
async def test_idempotent_sync(
    db_session: AsyncSession, warehouse_and_products, client_factory,
):
    ctx = warehouse_and_products
    async with client_factory(ctx["member"]) as client:
        r1 = await client.post("/api/stock-counts", json={
            "warehouse_id": str(ctx["warehouse"].id),
            "items": [{"product_id": str(ctx["p1"].id), "counted_qty": 8}],
        })
        cid = r1.json()["id"]
        await client.post(f"/api/stock-counts/{cid}/submit")
        s1 = await client.post(f"/api/stock-counts/{cid}/sync")
        s2 = await client.post(f"/api/stock-counts/{cid}/sync")
        assert s1.status_code == 200 and s2.status_code == 200
        assert s1.json() == s2.json()

    # Only ONE adjustment movement even though sync ran twice.
    rows = (await db_session.execute(
        select(StockMovement).where(
            StockMovement.product_id == ctx["p1"].id,
            StockMovement.type == StockMovementType.ADJUSTMENT,
        )
    )).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_org_isolation(
    db_session: AsyncSession, warehouse_and_products, two_orgs, client_factory,
):
    ctx = warehouse_and_products
    async with client_factory(ctx["member"]) as client:
        r1 = await client.post("/api/stock-counts", json={
            "warehouse_id": str(ctx["warehouse"].id),
            "items": [{"product_id": str(ctx["p1"].id), "counted_qty": 10}],
        })
        cid = r1.json()["id"]

    # Org B should not see count.
    async with client_factory(two_orgs["b"]["member"]) as client_b:
        list_res = await client_b.get("/api/stock-counts")
        assert list_res.status_code == 200
        assert all(row["id"] != cid for row in list_res.json())
        get_res = await client_b.get(f"/api/stock-counts/{cid}")
        assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_cancel_draft_stock_count(
    db_session: AsyncSession, warehouse_and_products, client_factory,
):
    ctx = warehouse_and_products
    async with client_factory(ctx["member"]) as client:
        r1 = await client.post("/api/stock-counts", json={
            "warehouse_id": str(ctx["warehouse"].id),
            "items": [],
        })
        cid = r1.json()["id"]
        res = await client.post(f"/api/stock-counts/{cid}/cancel")
        assert res.status_code == 200
        assert res.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_stock_count_analytics_summary(
    db_session: AsyncSession, warehouse_and_products, client_factory,
):
    ctx = warehouse_and_products
    async with client_factory(ctx["member"]) as client:
        r1 = await client.post("/api/stock-counts", json={
            "warehouse_id": str(ctx["warehouse"].id),
            "items": [
                {"product_id": str(ctx["p1"].id), "counted_qty": 13},
                {"product_id": str(ctx["p2"].id), "counted_qty": 2},
            ],
        })
        cid = r1.json()["id"]
        await client.post(f"/api/stock-counts/{cid}/submit")
        await client.post(f"/api/stock-counts/{cid}/sync")
        summary = await client.get("/api/analytics/stock-counts")
        assert summary.status_code == 200, summary.text
        body = summary.json()
        assert body["total"] >= 1
        assert body["synced"] >= 1
        assert body["total_positive_variance"] >= 3  # +3 on p1
        assert body["total_negative_variance"] <= -2  # -2 on p2


@pytest.mark.asyncio
async def test_variance_endpoint(
    db_session: AsyncSession, warehouse_and_products, client_factory,
):
    ctx = warehouse_and_products
    async with client_factory(ctx["member"]) as client:
        r1 = await client.post("/api/stock-counts", json={
            "warehouse_id": str(ctx["warehouse"].id),
            "items": [
                {"product_id": str(ctx["p1"].id), "counted_qty": 9},
            ],
        })
        cid = r1.json()["id"]
        await client.post(f"/api/stock-counts/{cid}/submit")
        res = await client.get(f"/api/analytics/stock-counts/{cid}/variance")
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["total_counted"] == 9
        assert body["total_expected"] == 10
        assert body["total_negative"] == -1


@pytest.mark.asyncio
async def test_audit_log_written(
    db_session: AsyncSession, warehouse_and_products, client_factory,
):
    ctx = warehouse_and_products
    async with client_factory(ctx["member"]) as client:
        r1 = await client.post("/api/stock-counts", json={
            "warehouse_id": str(ctx["warehouse"].id),
            "items": [{"product_id": str(ctx["p1"].id), "counted_qty": 10}],
        })
        cid = r1.json()["id"]
        await client.post(f"/api/stock-counts/{cid}/submit")
        await client.post(f"/api/stock-counts/{cid}/sync")

    entries = (await db_session.execute(
        select(AuditLogEntry).where(
            AuditLogEntry.target_id == cid,
            AuditLogEntry.org_id == ctx["org"].id,
        )
    )).scalars().all()
    actions = {e.action for e in entries}
    assert "STOCK_COUNT_CREATED" in actions
    assert "STOCK_COUNT_SUBMITTED" in actions
    assert "STOCK_COUNT_SYNCED" in actions


@pytest.mark.asyncio
async def test_scheduler_marks_stuck_counts(
    db_session: AsyncSession, warehouse_and_products, client_factory,
):
    ctx = warehouse_and_products
    async with client_factory(ctx["member"]) as client:
        r1 = await client.post("/api/stock-counts", json={
            "warehouse_id": str(ctx["warehouse"].id),
            "items": [{"product_id": str(ctx["p1"].id), "counted_qty": 10}],
        })
        cid = r1.json()["id"]
        await client.post(f"/api/stock-counts/{cid}/submit")

    # Back-date submitted_at so the sweep picks it up.
    sc = await db_session.get(StockCount, uuid.UUID(cid))
    sc.submitted_at = datetime.now(timezone.utc) - timedelta(hours=48)
    await db_session.commit()

    from app.features.inventory.stock_counts import mark_stuck_counts

    reset = await mark_stuck_counts(db_session, older_than_hours=24)
    assert reset >= 1
    await db_session.refresh(sc)
    assert sc.status == StockCountStatus.DRAFT
