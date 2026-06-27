"""Tests for Item 20 — Auto-create payable invoice on PO receipt."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.audit import AuditLogEntry
from app.models.inventory import (
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    StockLevel,
    Supplier,
    Warehouse,
)
from app.models.payable_invoice import PayableInvoice
from app.services.payables import create_payable_from_po




async def _seed_supplier(db, org_id, *, create_invoice_on_receipt: bool = False, name="Pay AB"):
    s = Supplier(
        org_id=org_id,
        name=name,
        create_invoice_on_receipt=create_invoice_on_receipt,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


async def _seed_product_and_warehouse(db, org_id, *, tax_rate: Decimal = Decimal("25.00")):
    wh = Warehouse(org_id=org_id, name="PAY-WH")
    db.add(wh)
    p = Product(
        org_id=org_id,
        name="Widget",
        sku=f"PAY-{uuid.uuid4().hex[:6]}",
        unit="st",
        purchase_price=Decimal("10.00"),
        sell_price=Decimal("20.00"),
        tax_rate=tax_rate,
    )
    db.add(p)
    await db.flush()
    db.add(StockLevel(org_id=org_id, product_id=p.id, warehouse_id=wh.id, quantity=0))
    await db.commit()
    await db.refresh(p)
    return p, wh


async def _seed_po(db, org_id, supplier_id, product_id, *, qty: int = 4, price: Decimal = Decimal("25.00")):
    po = PurchaseOrder(
        org_id=org_id,
        supplier_id=supplier_id,
        status=PurchaseOrderStatus.SENT,
        total=price * qty,
    )
    db.add(po)
    await db.flush()
    # Back-date so lead-time capture path also has work to do.
    po.created_at = datetime.now(timezone.utc) - timedelta(days=2)
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


async def _load_po_with_relations(db, po_id):
    from sqlalchemy.orm import selectinload

    return await db.scalar(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.items),
        )
        .where(PurchaseOrder.id == po_id)
    )


# ─────────────────────────────────────────────────────────────────────────────
# Service-level tests
# ─────────────────────────────────────────────────────────────────────────────

async def test_disabled_supplier_skips_creation(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    supplier = await _seed_supplier(db_session, org.id, create_invoice_on_receipt=False)
    product, _ = await _seed_product_and_warehouse(db_session, org.id)
    po = await _seed_po(db_session, org.id, supplier.id, product.id)
    po = await _load_po_with_relations(db_session, po.id)

    result = await create_payable_from_po(
        db_session, po, actor_user_id=two_orgs["a"]["user_id"]
    )
    assert result.created is False
    assert result.payable is None
    assert result.skipped_reason == "supplier_disabled"

    rows = (
        await db_session.execute(
            select(PayableInvoice).where(PayableInvoice.purchase_order_id == po.id)
        )
    ).scalars().all()
    assert rows == []


async def test_enabled_supplier_creates_draft(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    supplier = await _seed_supplier(db_session, org.id, create_invoice_on_receipt=True)
    product, _ = await _seed_product_and_warehouse(db_session, org.id)
    po = await _seed_po(db_session, org.id, supplier.id, product.id, qty=4, price=Decimal("25.00"))
    po = await _load_po_with_relations(db_session, po.id)

    result = await create_payable_from_po(
        db_session, po, actor_user_id=two_orgs["a"]["user_id"]
    )
    assert result.created is True
    assert result.payable is not None
    assert result.payable.status == "DRAFT"
    assert result.payable.supplier_id == supplier.id
    assert result.payable.purchase_order_id == po.id
    # 4 × 25 = 100 net, 25 % VAT = 25, total 125
    assert result.payable.subtotal == Decimal("100.00")
    assert result.payable.tax_amount == Decimal("25.00")
    assert result.payable.total == Decimal("125.00")
    assert result.payable.currency == "SEK"


async def test_idempotent_on_repeat_call(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    supplier = await _seed_supplier(db_session, org.id, create_invoice_on_receipt=True)
    product, _ = await _seed_product_and_warehouse(db_session, org.id)
    po = await _seed_po(db_session, org.id, supplier.id, product.id)
    po = await _load_po_with_relations(db_session, po.id)

    first = await create_payable_from_po(
        db_session, po, actor_user_id=two_orgs["a"]["user_id"]
    )
    await db_session.commit()
    second = await create_payable_from_po(
        db_session, po, actor_user_id=two_orgs["a"]["user_id"]
    )
    assert first.created is True
    assert second.created is False
    assert second.payable is not None
    assert second.payable.id == first.payable.id

    rows = (
        await db_session.execute(
            select(PayableInvoice).where(PayableInvoice.purchase_order_id == po.id)
        )
    ).scalars().all()
    assert len(rows) == 1


async def test_audit_entry_written_on_create(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    supplier = await _seed_supplier(db_session, org.id, create_invoice_on_receipt=True)
    product, _ = await _seed_product_and_warehouse(db_session, org.id)
    po = await _seed_po(db_session, org.id, supplier.id, product.id)
    po = await _load_po_with_relations(db_session, po.id)

    await create_payable_from_po(
        db_session, po, actor_user_id=two_orgs["a"]["user_id"]
    )
    await db_session.commit()

    entries = (
        await db_session.execute(
            select(AuditLogEntry).where(
                AuditLogEntry.org_id == org.id,
                AuditLogEntry.action == "PAYABLE_INVOICE_AUTO_CREATED",
            )
        )
    ).scalars().all()
    assert len(entries) == 1
    extra = entries[0].extra
    assert extra["purchase_order_id"] == str(po.id)
    assert extra["supplier_id"] == str(supplier.id)


async def test_mixed_vat_rates_compute_correctly(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    supplier = await _seed_supplier(db_session, org.id, create_invoice_on_receipt=True)
    product, _ = await _seed_product_and_warehouse(
        db_session, org.id, tax_rate=Decimal("12.00")
    )
    po = await _seed_po(db_session, org.id, supplier.id, product.id, qty=2, price=Decimal("50.00"))
    po = await _load_po_with_relations(db_session, po.id)

    result = await create_payable_from_po(
        db_session, po, actor_user_id=two_orgs["a"]["user_id"]
    )
    # 2 × 50 = 100 net, 12 % VAT = 12, total 112
    assert result.payable.subtotal == Decimal("100.00")
    assert result.payable.tax_amount == Decimal("12.00")
    assert result.payable.total == Decimal("112.00")


# ─────────────────────────────────────────────────────────────────────────────
# HTTP integration via PO receive endpoint
# ─────────────────────────────────────────────────────────────────────────────

async def test_po_receive_creates_payable_when_enabled(db_session, two_orgs, client_factory):
    org = two_orgs["a"]["org"]
    supplier = await _seed_supplier(db_session, org.id, create_invoice_on_receipt=True)
    product, _ = await _seed_product_and_warehouse(db_session, org.id)
    po = await _seed_po(db_session, org.id, supplier.id, product.id)

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.patch(
            f"/api/inventory/purchase-orders/{po.id}/status",
            json={"status": "RECEIVED"},
        )
    assert r.status_code == 200, r.text

    rows = (
        await db_session.execute(
            select(PayableInvoice).where(PayableInvoice.purchase_order_id == po.id)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "DRAFT"


async def test_po_receive_skips_payable_when_disabled(db_session, two_orgs, client_factory):
    org = two_orgs["a"]["org"]
    supplier = await _seed_supplier(db_session, org.id, create_invoice_on_receipt=False)
    product, _ = await _seed_product_and_warehouse(db_session, org.id)
    po = await _seed_po(db_session, org.id, supplier.id, product.id)

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.patch(
            f"/api/inventory/purchase-orders/{po.id}/status",
            json={"status": "RECEIVED"},
        )
    assert r.status_code == 200, r.text

    rows = (
        await db_session.execute(
            select(PayableInvoice).where(PayableInvoice.purchase_order_id == po.id)
        )
    ).scalars().all()
    assert rows == []


async def test_payable_list_endpoint_filters(db_session, two_orgs, client_factory):
    org = two_orgs["a"]["org"]
    supplier = await _seed_supplier(db_session, org.id, create_invoice_on_receipt=True)
    product, _ = await _seed_product_and_warehouse(db_session, org.id)
    po = await _seed_po(db_session, org.id, supplier.id, product.id)
    po = await _load_po_with_relations(db_session, po.id)
    await create_payable_from_po(
        db_session, po, actor_user_id=two_orgs["a"]["user_id"]
    )
    await db_session.commit()

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/inventory/payable-invoices")
        assert r.status_code == 200, r.text
        items = r.json()
        assert len(items) == 1
        assert items[0]["status"] == "DRAFT"

        r2 = await client.get(
            f"/api/inventory/payable-invoices?supplier_id={supplier.id}"
        )
        assert r2.status_code == 200
        assert len(r2.json()) == 1

        r3 = await client.get(
            f"/api/inventory/payable-invoices?supplier_id={uuid.uuid4()}"
        )
        assert r3.status_code == 200
        assert r3.json() == []
