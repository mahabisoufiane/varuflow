"""Auto-reorder service + router tests (v38 — Item 16)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.features.inventory.auto_reorder_models import AutoReorderRun
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
from app.features.compliance.audit_models import AuditLogEntry
from app.features.auth.organization import OrgRole
from sqlalchemy import select



async def _seed_warehouse(db, org_id) -> Warehouse:
    w = Warehouse(org_id=org_id, name="Main WH")
    db.add(w)
    await db.commit()
    await db.refresh(w)
    return w


async def _seed_supplier(
    db, org_id, *, name="Alpha Supplier", average_lead_days=None, default_lead_days=7
) -> Supplier:
    s = Supplier(
        org_id=org_id,
        name=name,
        default_lead_days=default_lead_days,
        average_lead_days=Decimal(str(average_lead_days)) if average_lead_days is not None else None,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


async def _seed_product(
    db,
    org_id,
    *,
    sku,
    name,
    reorder_level=10,
    purchase_price=50,
    auto_reorder_enabled=True,
    preferred_supplier_id=None,
    reorder_quantity=None,
    reorder_lead_buffer_days=3,
) -> Product:
    p = Product(
        org_id=org_id,
        name=name,
        sku=sku,
        unit="st",
        purchase_price=Decimal(str(purchase_price)),
        sell_price=Decimal(str(purchase_price)) * 2,
        reorder_level=reorder_level,
        auto_reorder_enabled=auto_reorder_enabled,
        preferred_supplier_id=preferred_supplier_id,
        reorder_quantity=reorder_quantity,
        reorder_lead_buffer_days=reorder_lead_buffer_days,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


async def _set_stock(db, org_id, product, warehouse, qty: int) -> None:
    sl = StockLevel(
        org_id=org_id,
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity=qty,
        min_threshold=0,
    )
    db.add(sl)
    await db.commit()


async def _enable_auto_reorder(db, org) -> None:
    org.auto_reorder_enabled = True
    await db.commit()


# ── Service-level tests ───────────────────────────────────────────────────


async def test_auto_reorder_creates_draft_po(db_session, two_orgs):
    from app.services.auto_reorder import run_auto_reorder

    org = two_orgs["a"]["org"]
    await _enable_auto_reorder(db_session, org)
    wh = await _seed_warehouse(db_session, org.id)
    sup = await _seed_supplier(db_session, org.id)
    p = await _seed_product(
        db_session, org.id, sku="P1", name="Widget",
        reorder_level=10, preferred_supplier_id=sup.id, reorder_quantity=25,
    )
    await _set_stock(db_session, org.id, p, wh, qty=3)

    with patch(
        "app.services.auto_reorder.send_auto_reorder_notification_email",
        new=AsyncMock(return_value=True),
    ):
        result = await run_auto_reorder(org.id, db_session, triggered_by="manual")

    assert result.purchase_orders_created == 1
    assert result.products_checked == 1
    assert len(result.pos_created) == 1

    po = await db_session.scalar(
        select(PurchaseOrder).where(PurchaseOrder.org_id == org.id)
    )
    assert po is not None
    assert po.status == PurchaseOrderStatus.DRAFT
    items = (
        await db_session.scalars(
            select(PurchaseOrderItem).where(
                PurchaseOrderItem.purchase_order_id == po.id
            )
        )
    ).all()
    assert len(items) == 1
    assert items[0].quantity == 25


async def test_auto_reorder_groups_by_supplier(db_session, two_orgs):
    from app.services.auto_reorder import run_auto_reorder

    org = two_orgs["a"]["org"]
    await _enable_auto_reorder(db_session, org)
    wh = await _seed_warehouse(db_session, org.id)
    s1 = await _seed_supplier(db_session, org.id, name="S1")
    s2 = await _seed_supplier(db_session, org.id, name="S2")

    for i, sup in enumerate([s1, s1, s2], start=1):
        p = await _seed_product(
            db_session, org.id, sku=f"P{i}", name=f"Prod{i}",
            reorder_level=10, preferred_supplier_id=sup.id, reorder_quantity=5,
        )
        await _set_stock(db_session, org.id, p, wh, qty=0)

    with patch(
        "app.services.auto_reorder.send_auto_reorder_notification_email",
        new=AsyncMock(return_value=True),
    ):
        result = await run_auto_reorder(org.id, db_session)

    assert result.purchase_orders_created == 2
    assert result.products_checked == 3

    pos = (
        await db_session.scalars(
            select(PurchaseOrder).where(PurchaseOrder.org_id == org.id)
        )
    ).all()
    assert len(pos) == 2
    counts = {po.supplier_id: 0 for po in pos}
    for po in pos:
        items = (
            await db_session.scalars(
                select(PurchaseOrderItem).where(
                    PurchaseOrderItem.purchase_order_id == po.id
                )
            )
        ).all()
        counts[po.supplier_id] = len(items)
    assert counts[s1.id] == 2
    assert counts[s2.id] == 1


async def test_auto_reorder_skips_product_without_supplier(db_session, two_orgs):
    from app.services.auto_reorder import run_auto_reorder

    org = two_orgs["a"]["org"]
    await _enable_auto_reorder(db_session, org)
    wh = await _seed_warehouse(db_session, org.id)
    p = await _seed_product(
        db_session, org.id, sku="NS", name="No supplier",
        reorder_level=10, preferred_supplier_id=None, reorder_quantity=5,
    )
    await _set_stock(db_session, org.id, p, wh, qty=0)

    result = await run_auto_reorder(org.id, db_session)
    assert result.purchase_orders_created == 0
    assert result.products_skipped == 1


async def test_auto_reorder_respects_product_disabled_flag(db_session, two_orgs):
    from app.services.auto_reorder import run_auto_reorder

    org = two_orgs["a"]["org"]
    await _enable_auto_reorder(db_session, org)
    wh = await _seed_warehouse(db_session, org.id)
    sup = await _seed_supplier(db_session, org.id)
    p = await _seed_product(
        db_session, org.id, sku="DIS", name="Disabled",
        reorder_level=10, preferred_supplier_id=sup.id,
        reorder_quantity=5, auto_reorder_enabled=False,
    )
    await _set_stock(db_session, org.id, p, wh, qty=0)

    result = await run_auto_reorder(org.id, db_session)
    assert result.purchase_orders_created == 0
    assert result.products_skipped == 1


async def test_auto_reorder_respects_org_disabled_flag(db_session, two_orgs):
    from app.services.auto_reorder import run_auto_reorder

    org = two_orgs["a"]["org"]
    # Leave org.auto_reorder_enabled at default (False).
    wh = await _seed_warehouse(db_session, org.id)
    sup = await _seed_supplier(db_session, org.id)
    p = await _seed_product(
        db_session, org.id, sku="ORG", name="Org off",
        reorder_level=10, preferred_supplier_id=sup.id, reorder_quantity=5,
    )
    await _set_stock(db_session, org.id, p, wh, qty=0)

    result = await run_auto_reorder(org.id, db_session)
    assert result.purchase_orders_created == 0


async def test_auto_reorder_uses_qty_override(db_session, two_orgs):
    from app.services.auto_reorder import run_auto_reorder

    org = two_orgs["a"]["org"]
    await _enable_auto_reorder(db_session, org)
    wh = await _seed_warehouse(db_session, org.id)
    sup = await _seed_supplier(db_session, org.id)
    p = await _seed_product(
        db_session, org.id, sku="OV", name="Overridden",
        reorder_level=10, preferred_supplier_id=sup.id, reorder_quantity=50,
    )
    await _set_stock(db_session, org.id, p, wh, qty=1)

    with patch(
        "app.services.auto_reorder.send_auto_reorder_notification_email",
        new=AsyncMock(return_value=True),
    ):
        await run_auto_reorder(org.id, db_session)

    item = await db_session.scalar(
        select(PurchaseOrderItem).join(PurchaseOrder).where(
            PurchaseOrder.org_id == org.id
        )
    )
    assert item is not None
    assert item.quantity == 50


async def test_auto_reorder_uses_formula_when_no_override(db_session, two_orgs):
    from app.services.auto_reorder import run_auto_reorder

    org = two_orgs["a"]["org"]
    await _enable_auto_reorder(db_session, org)
    wh = await _seed_warehouse(db_session, org.id)
    sup = await _seed_supplier(
        db_session, org.id, default_lead_days=7, average_lead_days=None,
    )
    p = await _seed_product(
        db_session, org.id, sku="F", name="Formula",
        reorder_level=10, preferred_supplier_id=sup.id, reorder_quantity=None,
        reorder_lead_buffer_days=3,
    )
    await _set_stock(db_session, org.id, p, wh, qty=2)

    with patch(
        "app.services.auto_reorder.send_auto_reorder_notification_email",
        new=AsyncMock(return_value=True),
    ):
        await run_auto_reorder(org.id, db_session)

    item = await db_session.scalar(
        select(PurchaseOrderItem).join(PurchaseOrder).where(
            PurchaseOrder.org_id == org.id
        )
    )
    assert item is not None
    # reorder_level * 2 - current = 18; no OUT movements → consumption
    # branch resolves to 0. Formula picks max(18, 0) = 18.
    assert item.quantity == 18


async def test_auto_reorder_records_run(db_session, two_orgs):
    from app.services.auto_reorder import run_auto_reorder

    org = two_orgs["a"]["org"]
    await _enable_auto_reorder(db_session, org)
    # No eligible products — still records a run row.
    result = await run_auto_reorder(org.id, db_session, triggered_by="manual")
    assert result.products_checked == 0

    rows = (
        await db_session.scalars(
            select(AutoReorderRun).where(AutoReorderRun.org_id == org.id)
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].triggered_by == "manual"
    assert rows[0].status == "completed"


async def test_auto_reorder_sends_notification_email(db_session, two_orgs):
    from app.services.auto_reorder import run_auto_reorder

    org = two_orgs["a"]["org"]
    await _enable_auto_reorder(db_session, org)
    org.auto_reorder_notify_email = "owner@example.com"
    await db_session.commit()
    wh = await _seed_warehouse(db_session, org.id)
    sup = await _seed_supplier(db_session, org.id)
    p = await _seed_product(
        db_session, org.id, sku="E", name="Email",
        reorder_level=10, preferred_supplier_id=sup.id, reorder_quantity=5,
    )
    await _set_stock(db_session, org.id, p, wh, qty=0)

    send = AsyncMock(return_value=True)
    with patch("app.services.auto_reorder.send_auto_reorder_notification_email", new=send):
        await run_auto_reorder(org.id, db_session)
    assert send.await_count == 1
    kwargs = send.await_args.kwargs
    assert kwargs["to_email"] == "owner@example.com"
    assert kwargs["org_name"] == org.name
    assert len(kwargs["pos"]) == 1


async def test_audit_log_written_per_po(db_session, two_orgs):
    from app.services.auto_reorder import run_auto_reorder

    org = two_orgs["a"]["org"]
    await _enable_auto_reorder(db_session, org)
    wh = await _seed_warehouse(db_session, org.id)
    s1 = await _seed_supplier(db_session, org.id, name="AuditS1")
    s2 = await _seed_supplier(db_session, org.id, name="AuditS2")
    for i, sup in enumerate([s1, s2], start=1):
        p = await _seed_product(
            db_session, org.id, sku=f"AU{i}", name=f"AU{i}",
            reorder_level=10, preferred_supplier_id=sup.id, reorder_quantity=4,
        )
        await _set_stock(db_session, org.id, p, wh, qty=0)

    with patch(
        "app.services.auto_reorder.send_auto_reorder_notification_email",
        new=AsyncMock(return_value=True),
    ):
        await run_auto_reorder(org.id, db_session)

    rows = (
        await db_session.scalars(
            select(AuditLogEntry).where(
                AuditLogEntry.org_id == org.id,
                AuditLogEntry.action == "purchase_order.auto_created",
            )
        )
    ).all()
    assert len(rows) == 2


# ── Router / HTTP tests ──────────────────────────────────────────────────


async def test_manual_trigger_requires_owner(db_session, two_orgs, client_factory):
    org = two_orgs["a"]["org"]
    await _enable_auto_reorder(db_session, org)

    member = two_orgs["a"]["member"]
    member.role = OrgRole.MEMBER
    await db_session.commit()

    async with client_factory(member) as client:
        r = await client.post("/api/auto-reorder/run")
    assert r.status_code == 403


async def test_preview_returns_correct_products(db_session, two_orgs, client_factory):
    org = two_orgs["a"]["org"]
    await _enable_auto_reorder(db_session, org)
    wh = await _seed_warehouse(db_session, org.id)
    sup = await _seed_supplier(db_session, org.id)
    p1 = await _seed_product(
        db_session, org.id, sku="PV1", name="Preview 1",
        reorder_level=10, preferred_supplier_id=sup.id, reorder_quantity=5,
    )
    p2 = await _seed_product(
        db_session, org.id, sku="PV2", name="Preview 2",
        reorder_level=20, preferred_supplier_id=sup.id, reorder_quantity=7,
    )
    await _set_stock(db_session, org.id, p1, wh, qty=0)
    await _set_stock(db_session, org.id, p2, wh, qty=1)
    # Also seed a product that is NOT below reorder — preview should skip it.
    p_ok = await _seed_product(
        db_session, org.id, sku="OK", name="Healthy",
        reorder_level=10, preferred_supplier_id=sup.id, reorder_quantity=5,
    )
    await _set_stock(db_session, org.id, p_ok, wh, qty=500)

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/auto-reorder/preview")
    assert r.status_code == 200
    lines = r.json()
    returned = {l["sku"] for l in lines}
    assert "PV1" in returned and "PV2" in returned
    assert "OK" not in returned
