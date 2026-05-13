"""Tests for Feature 13 — B2B self-service portal ordering.

Covers the catalogue endpoint (per-customer price overrides, soft
reservation netting), order placement (DRAFT invoice + RESERVED stock
movements + audit), opt-in enforcement, warehouse requirement, tenant
isolation, and order history status mapping.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.main import app
from app.models.audit import AuditLogEntry
from app.models.customer_price_override import CustomerPriceOverride
from app.models.inventory import (
    Product,
    StockLevel,
    StockMovement,
    StockMovementType,
    Warehouse,
)
from app.models.invoicing import (
    Customer,
    CustomerPortalToken,
    Invoice,
    InvoiceLineItem,
    InvoiceStatus,
)
from app.models.organization import Organization




async def _postgres_ok(db):
    try:
        await db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _login(customer: Customer, org: Organization, db) -> str:
    """Issue a magic link, exchange it, return the portal JWT."""
    raw = secrets.token_urlsafe(32)
    db.add(CustomerPortalToken(
        customer_id=customer.id,
        org_id=org.id,
        token=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    ))
    await db.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get(f"/api/portal/auth/verify?token={raw}")
    assert r.status_code == 200, r.text
    return r.json()["portal_token"]


@pytest_asyncio.fixture
async def ordering_fixture(db_session):
    if not await _postgres_ok(db_session):
        pytest.skip("PostgreSQL not reachable")

    org = Organization(
        id=uuid.uuid4(), name="Seller AB", org_number="556000-0020",
        orders_notification_email="orders@seller.test",
    )
    db_session.add(org)
    await db_session.commit()

    customer = Customer(
        org_id=org.id,
        company_name="Buyer AB",
        email="buyer@ordering.test",
        portal_ordering_enabled=True,
        payment_terms_days=30,
    )
    db_session.add(customer)

    warehouse = Warehouse(org_id=org.id, name="Main", is_active=True)
    db_session.add(warehouse)

    product_a = Product(
        org_id=org.id, name="Widget A", sku="WID-A", unit="st",
        purchase_price=Decimal("50.00"), sell_price=Decimal("100.00"),
        tax_rate=Decimal("25.00"), is_active=True,
    )
    product_b = Product(
        org_id=org.id, name="Widget B", sku="WID-B", unit="st",
        purchase_price=Decimal("80.00"), sell_price=Decimal("200.00"),
        tax_rate=Decimal("25.00"), is_active=True,
    )
    db_session.add_all([product_a, product_b])
    await db_session.commit()

    # Stock on hand: 10 A, 5 B.
    db_session.add_all([
        StockLevel(org_id=org.id, product_id=product_a.id, warehouse_id=warehouse.id, quantity=10),
        StockLevel(org_id=org.id, product_id=product_b.id, warehouse_id=warehouse.id, quantity=5),
    ])
    # Negotiated price for A only.
    db_session.add(CustomerPriceOverride(
        org_id=org.id, customer_id=customer.id, product_id=product_a.id,
        override_price=Decimal("90.00"),
    ))
    await db_session.commit()

    yield {
        "org": org, "customer": customer, "warehouse": warehouse,
        "product_a": product_a, "product_b": product_b,
    }

    await db_session.delete(org)
    await db_session.commit()


async def test_catalogue_returns_products_with_overrides_and_stock(ordering_fixture, db_session):
    org = ordering_fixture["org"]
    customer = ordering_fixture["customer"]
    product_a = ordering_fixture["product_a"]

    token = await _login(customer, org, db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/portal/catalogue", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ordering_enabled"] is True
    by_sku = {it["sku"]: it for it in body["items"]}
    assert by_sku["WID-A"]["price_is_override"] is True
    assert Decimal(by_sku["WID-A"]["price"]) == Decimal("90.00")
    assert by_sku["WID-A"]["stock_available"] == 10
    assert by_sku["WID-B"]["price_is_override"] is False
    assert Decimal(by_sku["WID-B"]["price"]) == Decimal("200.00")
    assert by_sku["WID-B"]["stock_available"] == 5

    # A pre-existing RESERVED movement should net out of the available qty.
    db_session.add(StockMovement(
        org_id=org.id, product_id=product_a.id,
        warehouse_id=ordering_fixture["warehouse"].id,
        type=StockMovementType.RESERVED, quantity=3, reference="PRE",
    ))
    await db_session.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r2 = await c.get("/api/portal/catalogue", headers={"Authorization": f"Bearer {token}"})
    by_sku = {it["sku"]: it for it in r2.json()["items"]}
    assert by_sku["WID-A"]["stock_available"] == 7


async def test_place_order_creates_draft_invoice_and_reserves_stock(ordering_fixture, db_session):
    org = ordering_fixture["org"]
    customer = ordering_fixture["customer"]
    product_a = ordering_fixture["product_a"]
    product_b = ordering_fixture["product_b"]

    token = await _login(customer, org, db_session)
    payload = {
        "lines": [
            {"product_id": str(product_a.id), "quantity": 2},
            {"product_id": str(product_b.id), "quantity": 1},
        ],
        "notes": "Please rush",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/portal/orders", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["order_number"].startswith("INV-")
    # A: 2 × 90 override = 180; B: 1 × 200 = 200. Subtotal 380, VAT 25% = 95 → 475.
    assert Decimal(body["total_sek"]) == Decimal("475.00")

    invoice_id = uuid.UUID(body["invoice_id"])
    inv = await db_session.get(Invoice, invoice_id)
    assert inv is not None
    assert inv.status == InvoiceStatus.DRAFT
    assert inv.customer_id == customer.id
    assert inv.notes == "Please rush"

    items = (await db_session.execute(
        select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice_id)
    )).scalars().all()
    assert len(items) == 2

    reserved = (await db_session.execute(
        select(StockMovement).where(
            StockMovement.org_id == org.id,
            StockMovement.type == StockMovementType.RESERVED,
            StockMovement.reference == body["order_number"],
        )
    )).scalars().all()
    assert len(reserved) == 2
    assert sum(m.quantity for m in reserved) == 3

    audits = (await db_session.execute(
        select(AuditLogEntry).where(
            AuditLogEntry.action == "ORDER_PLACED_BY_PORTAL",
            AuditLogEntry.org_id == org.id,
            AuditLogEntry.target_id == str(invoice_id),
        )
    )).scalars().all()
    assert len(audits) == 1


async def test_order_blocked_when_toggle_disabled(ordering_fixture, db_session):
    customer = ordering_fixture["customer"]
    org = ordering_fixture["org"]
    product_a = ordering_fixture["product_a"]

    customer.portal_ordering_enabled = False
    await db_session.commit()

    token = await _login(customer, org, db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/portal/orders",
            json={"lines": [{"product_id": str(product_a.id), "quantity": 1}]},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 403


async def test_order_rejects_duplicate_product(ordering_fixture, db_session):
    customer = ordering_fixture["customer"]
    org = ordering_fixture["org"]
    product_a = ordering_fixture["product_a"]

    token = await _login(customer, org, db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/portal/orders",
            json={"lines": [
                {"product_id": str(product_a.id), "quantity": 1},
                {"product_id": str(product_a.id), "quantity": 2},
            ]},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 400


async def test_order_rejects_foreign_product(ordering_fixture, db_session):
    """A product owned by a different org must not be orderable."""
    other_org = Organization(
        id=uuid.uuid4(), name="Other AB", org_number="556000-0099",
    )
    db_session.add(other_org)
    await db_session.commit()
    foreign = Product(
        org_id=other_org.id, name="Foreign", sku="FOR-1", unit="st",
        purchase_price=Decimal("1"), sell_price=Decimal("1"),
        tax_rate=Decimal("25.00"), is_active=True,
    )
    db_session.add(foreign)
    await db_session.commit()

    customer = ordering_fixture["customer"]
    org = ordering_fixture["org"]
    token = await _login(customer, org, db_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/api/portal/orders",
                json={"lines": [{"product_id": str(foreign.id), "quantity": 1}]},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 400
    finally:
        await db_session.delete(other_org)
        await db_session.commit()


async def test_orders_history_maps_statuses(ordering_fixture, db_session):
    org = ordering_fixture["org"]
    customer = ordering_fixture["customer"]

    from datetime import date
    today = date.today()
    invs = [
        Invoice(
            org_id=org.id, customer_id=customer.id,
            invoice_number=f"INV-TEST-{i}",
            issue_date=today, due_date=today + timedelta(days=30),
            status=st,
            subtotal=Decimal("100.00"), vat_amount=Decimal("25.00"),
            total_sek=Decimal("125.00"),
        )
        for i, st in enumerate((InvoiceStatus.DRAFT, InvoiceStatus.SENT, InvoiceStatus.PAID), 1)
    ]
    db_session.add_all(invs)
    await db_session.commit()

    token = await _login(customer, org, db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/portal/orders", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    body = r.json()
    status_by_number = {row["order_number"]: row["status"] for row in body}
    assert status_by_number["INV-TEST-1"] == "pending"
    assert status_by_number["INV-TEST-2"] == "confirmed"
    assert status_by_number["INV-TEST-3"] == "invoiced"
