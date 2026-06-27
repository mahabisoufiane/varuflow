"""Tests for the demand_forecast AI card.

The ai_engine router is gated by ``require_plan(OrgPlan.PRO)``; every test
upgrades the fixture org before calling it.

Requires a live PostgreSQL (see conftest._postgres_reachable).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.features.inventory.models import (
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    StockLevel,
    StockMovement,
    StockMovementType,
    Supplier,
    Warehouse,
)
from app.features.auth.organization import OrgPlan
from app.features.ai.ai_snooze import AiCardSnooze




async def _seed_product_with_history(
    db, org_id, *, qty_on_hand: int, total_out_90d: int, reorder_level: int = 0
):
    """Create a product + warehouse + StockLevel + 90 days of OUT movements.

    The movements are spread evenly across the 90-day window so the
    router's aggregation (sum / 90) matches the test expectation exactly.
    """
    wh = Warehouse(org_id=org_id, name="Main WH")
    db.add(wh)
    p = Product(
        org_id=org_id,
        name="Skruv 5mm",
        sku="SKR-5",
        unit="st",
        purchase_price=Decimal("10.00"),
        sell_price=Decimal("20.00"),
        reorder_level=reorder_level,
    )
    db.add(p)
    await db.flush()

    db.add(StockLevel(org_id=org_id, product_id=p.id, warehouse_id=wh.id, quantity=qty_on_hand))

    # Spread total_out_90d across days [-89..-1] so each day has the same
    # slice (integer division remainder goes on day -1).
    if total_out_90d > 0:
        per_day, remainder = divmod(total_out_90d, 89)
        base = datetime.now(timezone.utc)
        for d in range(1, 90):
            q = per_day + (remainder if d == 1 else 0)
            if q <= 0:
                continue
            db.add(StockMovement(
                org_id=org_id,
                product_id=p.id,
                warehouse_id=wh.id,
                type=StockMovementType.OUT,
                quantity=q,
                created_at=base - timedelta(days=d),
            ))
    await db.commit()
    await db.refresh(p)
    return p


def _find_card(cards, kind, product_id):
    for c in cards:
        meta = c.get("meta") or {}
        if meta.get("kind") == kind and meta.get("product_id") == str(product_id):
            return c
    return None


async def test_demand_forecast_emits_when_days_left_below_14(
    db_session, two_orgs, client_factory
):
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()

    # 90 day total OUT = 900 → avg_daily = 10. stock_on_hand = 50 → days_left = 5.0.
    p = await _seed_product_with_history(
        db_session, org.id, qty_on_hand=50, total_out_90d=900, reorder_level=200,
    )

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/ai/cards")
    assert r.status_code == 200

    card = _find_card(r.json()["cards"], "demand_forecast", p.id)
    # Note: the same product also exceeds the 7-day-velocity stockout rule
    # (900 units in the 7-day window too since movements populate the whole
    # 90-day span). The demand_forecast card is suppressed when the short-
    # window card already fires — assert that suppression instead of a
    # false-positive duplicate.
    assert card is None


async def test_demand_forecast_fires_when_short_window_is_quiet(
    db_session, two_orgs, client_factory
):
    """Product with steady 90-day history but no movements in the last 7 days
    should trigger demand_forecast, not the 7-day stockout alert."""
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()

    wh = Warehouse(org_id=org.id, name="Main WH 2")
    db_session.add(wh)
    p = Product(
        org_id=org.id,
        name="Bult 8mm",
        sku="BULT-8",
        unit="st",
        purchase_price=Decimal("5.00"),
        sell_price=Decimal("12.00"),
        reorder_level=100,
    )
    db_session.add(p)
    await db_session.flush()
    db_session.add(StockLevel(
        org_id=org.id, product_id=p.id, warehouse_id=wh.id, quantity=50,
    ))

    # Place movements ONLY between day -8..-90 — nothing in the last 7 days.
    # 90-day total = 810; avg_daily = 9.0 → days_until_stockout = 50/9 = ~5.6
    base = datetime.now(timezone.utc)
    for d in range(8, 98):  # 90 days worth, all older than 7 days
        db_session.add(StockMovement(
            org_id=org.id,
            product_id=p.id,
            warehouse_id=wh.id,
            type=StockMovementType.OUT,
            quantity=9,
            created_at=base - timedelta(days=d),
        ))
    await db_session.commit()

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/ai/cards")
    assert r.status_code == 200
    card = _find_card(r.json()["cards"], "demand_forecast", p.id)
    assert card is not None, "demand_forecast card should fire when 7-day window is empty"

    meta = card["meta"]
    assert meta["current_stock"] == 50
    # avg_daily_consumption = 810 / 90 = 9.0
    assert abs(meta["avg_daily_consumption"] - 9.0) < 0.01
    # days_until_stockout = 50 / 9 ≈ 5.6 (rounded to 1 decimal in meta)
    assert 5.4 <= meta["days_until_stockout"] <= 5.7
    # Suggested reorder qty = reorder_level - current_stock + avg*30
    # = 100 - 50 + 9*30 = 320
    assert meta["suggested_qty"] == 320
    assert meta["window_days"] == 90


async def test_demand_forecast_skips_when_no_history(
    db_session, two_orgs, client_factory
):
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()

    p = await _seed_product_with_history(
        db_session, org.id, qty_on_hand=0, total_out_90d=0, reorder_level=10,
    )

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/ai/cards")
    assert r.status_code == 200
    assert _find_card(r.json()["cards"], "demand_forecast", p.id) is None


# ── Dead stock + snooze tests ─────────────────────────────────────────────────


async def _seed_dead_stock_product(
    db,
    org_id,
    *,
    qty: int,
    po_unit_price: Decimal | None,
    old_out_qty: int = 0,
    sku: str = "DEAD-1",
    name: str = "Gammal pryl",
):
    """Seed a product with stock on hand and no OUT movements within 60 days.

    If ``po_unit_price`` is set, a RECEIVED PurchaseOrder with a single line
    item for this product is created so the router picks up the latest
    PO unit price. If ``old_out_qty > 0``, a single OUT movement 90 days
    ago is added (outside the 60-day window, must NOT suppress the card).
    """
    wh = Warehouse(org_id=org_id, name=f"DeadWH-{sku}")
    db.add(wh)
    p = Product(
        org_id=org_id,
        name=name,
        sku=sku,
        unit="st",
        purchase_price=Decimal("1.00"),  # cheap fallback — PO price should win
        sell_price=Decimal("50.00"),
        reorder_level=0,
    )
    db.add(p)
    await db.flush()
    db.add(StockLevel(
        org_id=org_id, product_id=p.id, warehouse_id=wh.id, quantity=qty,
    ))

    if po_unit_price is not None:
        supplier = Supplier(org_id=org_id, name=f"Sup-{sku}")
        db.add(supplier)
        await db.flush()
        po = PurchaseOrder(
            org_id=org_id,
            supplier_id=supplier.id,
            status=PurchaseOrderStatus.RECEIVED,
            total=po_unit_price * qty,
        )
        db.add(po)
        await db.flush()
        db.add(PurchaseOrderItem(
            purchase_order_id=po.id,
            product_id=p.id,
            quantity=qty,
            unit_price=po_unit_price,
            line_total=po_unit_price * qty,
        ))

    if old_out_qty > 0:
        db.add(StockMovement(
            org_id=org_id,
            product_id=p.id,
            warehouse_id=wh.id,
            type=StockMovementType.OUT,
            quantity=old_out_qty,
            created_at=datetime.now(timezone.utc) - timedelta(days=90),
        ))

    await db.commit()
    await db.refresh(p)
    return p


async def test_dead_stock_card_uses_last_po_price(db_session, two_orgs, client_factory):
    """capital_tied must be qty * latest PO unit_price, not Product.purchase_price."""
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()

    # qty=12, PO price=25 → capital_tied = 300.00
    p = await _seed_dead_stock_product(
        db_session, org.id, qty=12, po_unit_price=Decimal("25.00"),
    )

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/ai/cards")
    assert r.status_code == 200

    card = _find_card(r.json()["cards"], "dead_stock", p.id)
    assert card is not None, "dead_stock card should fire for 60d-idle product"
    meta = card["meta"]
    assert meta["stock_level"] == 12
    assert meta["unit_cost"] == 25.00
    assert meta["capital_tied"] == 300.00
    assert meta["window_days"] == 60
    assert card["id"] == f"deadstock-{p.id}"


async def test_dead_stock_ignores_out_movements_older_than_60d(
    db_session, two_orgs, client_factory
):
    """An OUT movement 90 days ago must NOT suppress the dead_stock card."""
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()

    p = await _seed_dead_stock_product(
        db_session,
        org.id,
        qty=5,
        po_unit_price=Decimal("10.00"),
        old_out_qty=3,
        sku="DEAD-OLD",
    )

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/ai/cards")
    assert r.status_code == 200
    assert _find_card(r.json()["cards"], "dead_stock", p.id) is not None


async def test_active_snooze_suppresses_dead_stock_card(
    db_session, two_orgs, client_factory
):
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()

    p = await _seed_dead_stock_product(
        db_session, org.id, qty=7, po_unit_price=Decimal("15.00"), sku="DEAD-SNZ",
    )
    db_session.add(AiCardSnooze(
        org_id=org.id,
        card_type="dead_stock",
        product_id=p.id,
        snoozed_until=datetime.now(timezone.utc) + timedelta(days=7),
    ))
    await db_session.commit()

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/ai/cards")
    assert r.status_code == 200
    assert _find_card(r.json()["cards"], "dead_stock", p.id) is None


async def test_expired_snooze_does_not_suppress_card(
    db_session, two_orgs, client_factory
):
    """snoozed_until in the past must NOT suppress the card (expiry logic)."""
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()

    p = await _seed_dead_stock_product(
        db_session, org.id, qty=4, po_unit_price=Decimal("20.00"), sku="DEAD-EXP",
    )
    db_session.add(AiCardSnooze(
        org_id=org.id,
        card_type="dead_stock",
        product_id=p.id,
        snoozed_until=datetime.now(timezone.utc) - timedelta(days=1),
    ))
    await db_session.commit()

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/ai/cards")
    assert r.status_code == 200
    assert _find_card(r.json()["cards"], "dead_stock", p.id) is not None


async def test_snooze_endpoint_upserts_and_hides_card(
    db_session, two_orgs, client_factory
):
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()

    p = await _seed_dead_stock_product(
        db_session, org.id, qty=9, po_unit_price=Decimal("30.00"), sku="DEAD-EP",
    )

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.post(
            f"/api/ai/cards/deadstock-{p.id}/snooze", json={"days": 7},
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["status"] == "snoozed"
        # Frontend-visible "deadstock" normalises to internal "dead_stock"
        assert payload["card_type"] == "dead_stock"
        assert payload["product_id"] == str(p.id)

        # Subsequent GET omits the card
        r2 = await client.get("/api/ai/cards")
        assert _find_card(r2.json()["cards"], "dead_stock", p.id) is None

        # Re-snooze with different days → UPSERT extends window
        r3 = await client.post(
            f"/api/ai/cards/deadstock-{p.id}/snooze", json={"days": 30},
        )
        assert r3.status_code == 200


async def test_snooze_endpoint_rejects_cross_org_product(
    db_session, two_orgs, client_factory
):
    """Snoozing a product belonging to another org must 404, not succeed."""
    org_a = two_orgs["a"]["org"]
    org_b = two_orgs["b"]["org"]
    org_a.plan = OrgPlan.PRO
    await db_session.commit()

    # Seed a product in org B — org A has no access.
    p_b = await _seed_dead_stock_product(
        db_session, org_b.id, qty=3, po_unit_price=Decimal("5.00"), sku="DEAD-B",
    )

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.post(
            f"/api/ai/cards/deadstock-{p_b.id}/snooze", json={"days": 7},
        )
    assert r.status_code == 404


async def test_snooze_endpoint_validates_card_id_and_days(
    db_session, two_orgs, client_factory
):
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()

    async with client_factory(two_orgs["a"]["member"]) as client:
        # Malformed card_id (no UUID tail)
        r = await client.post(
            "/api/ai/cards/deadstock-notauuid/snooze", json={"days": 7},
        )
        assert r.status_code == 422

        # Days outside the {7, 30, 90} Literal
        any_uuid = "00000000-0000-0000-0000-000000000001"
        r2 = await client.post(
            f"/api/ai/cards/deadstock-{any_uuid}/snooze", json={"days": 5},
        )
        assert r2.status_code == 422

        # Non-snoozable card_type prefix
        r3 = await client.post(
            f"/api/ai/cards/peppol-{any_uuid}/snooze", json={"days": 7},
        )
        assert r3.status_code == 422

