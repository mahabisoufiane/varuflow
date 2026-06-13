"""Tests for gross margin analytics (Feature 8)."""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.inventory import Product
from app.models.invoicing import (
    Customer,
    Invoice,
    InvoiceLineItem,
    InvoiceStatus,
)
from app.models.organization import OrgPlan




async def _seed_customer(db, org_id) -> Customer:
    c = Customer(org_id=org_id, company_name="Kund AB", email="kund@test.local")
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _seed_product(db, org_id, *, sku, name, purchase, sell, category=None) -> Product:
    p = Product(
        org_id=org_id,
        name=name,
        sku=sku,
        unit="st",
        purchase_price=Decimal(str(purchase)),
        sell_price=Decimal(str(sell)),
        category=category,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


async def _seed_invoice_with_line(
    db, org_id, customer_id, *,
    product: Product | None,
    quantity: Decimal,
    unit_price: Decimal,
    issue_date: date | None = None,
    status: InvoiceStatus = InvoiceStatus.SENT,
) -> Invoice:
    today = issue_date or date.today()
    line_total = (quantity * unit_price).quantize(Decimal("0.01"))
    inv = Invoice(
        org_id=org_id,
        customer_id=customer_id,
        invoice_number=f"INV-{uuid.uuid4().hex[:8].upper()}",
        issue_date=today,
        due_date=today + timedelta(days=30),
        status=status,
        subtotal=line_total,
        vat_amount=Decimal("0.00"),
        total_sek=line_total,
    )
    db.add(inv)
    await db.flush()
    db.add(InvoiceLineItem(
        invoice_id=inv.id,
        product_id=product.id if product else None,
        description=product.name if product else "Service",
        quantity=quantity,
        unit_price=unit_price,
        tax_rate=Decimal("25.00"),
        line_total=line_total,
    ))
    await db.commit()
    await db.refresh(inv)
    return inv


async def test_margins_overall_math(db_session, two_orgs, client_factory):
    """Overall revenue / COGS / margin math for a simple 2-product mix."""
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()

    customer = await _seed_customer(db_session, org.id)
    # Product A: buy @ 40, sell @ 100 → 60% margin
    p_a = await _seed_product(
        db_session, org.id, sku="A", name="Produkt A",
        purchase=40, sell=100, category="tools",
    )
    # Product B: buy @ 80, sell @ 100 → 20% margin
    p_b = await _seed_product(
        db_session, org.id, sku="B", name="Produkt B",
        purchase=80, sell=100, category="food",
    )
    await _seed_invoice_with_line(
        db_session, org.id, customer.id, product=p_a,
        quantity=Decimal("10"), unit_price=Decimal("100.00"),
    )
    await _seed_invoice_with_line(
        db_session, org.id, customer.id, product=p_b,
        quantity=Decimal("5"), unit_price=Decimal("100.00"),
    )
    # Revenue = 1000 + 500 = 1500; COGS = 400 + 400 = 800; GP = 700; margin = 46.67%

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/analytics/margins")
    assert r.status_code == 200, r.text
    body = r.json()
    ov = body["overall"]
    assert float(ov["revenue"]) == 1500.00
    assert float(ov["cogs"]) == 800.00
    assert float(ov["gross_profit"]) == 700.00
    assert 46.6 <= ov["margin_pct"] <= 46.7
    assert ov["line_item_count"] == 2


async def test_margins_per_product_and_ranking(
    db_session, two_orgs, client_factory,
):
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()

    customer = await _seed_customer(db_session, org.id)
    p_high = await _seed_product(
        db_session, org.id, sku="HIGH", name="High margin",
        purchase=10, sell=100, category="tools",
    )
    p_low = await _seed_product(
        db_session, org.id, sku="LOW", name="Low margin",
        purchase=95, sell=100, category="food",
    )
    await _seed_invoice_with_line(
        db_session, org.id, customer.id, product=p_high,
        quantity=Decimal("1"), unit_price=Decimal("100.00"),
    )
    await _seed_invoice_with_line(
        db_session, org.id, customer.id, product=p_low,
        quantity=Decimal("1"), unit_price=Decimal("100.00"),
    )

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/analytics/margins")
    assert r.status_code == 200
    body = r.json()

    assert body["top_products"][0]["sku"] == "HIGH"
    assert body["worst_products"][0]["sku"] == "LOW"

    cats = {c["category"]: c for c in body["by_category"]}
    assert cats["tools"]["margin_pct"] >= 89
    assert cats["food"]["margin_pct"] <= 6


async def test_margins_service_line_without_product_counts_revenue_only(
    db_session, two_orgs, client_factory,
):
    """A line with product_id=NULL is treated as 0 COGS (service line)."""
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()

    customer = await _seed_customer(db_session, org.id)
    await _seed_invoice_with_line(
        db_session, org.id, customer.id, product=None,
        quantity=Decimal("2"), unit_price=Decimal("500.00"),
    )

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/analytics/margins")
    body = r.json()
    assert float(body["overall"]["revenue"]) == 1000.00
    assert float(body["overall"]["cogs"]) == 0.00
    assert float(body["overall"]["margin_pct"]) == 100.0
    # Service lines don't appear in product rankings (no product_id).
    assert body["top_products"] == []


async def test_margins_excludes_draft_invoices(
    db_session, two_orgs, client_factory,
):
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()

    customer = await _seed_customer(db_session, org.id)
    p = await _seed_product(
        db_session, org.id, sku="D", name="Draft prod",
        purchase=10, sell=100,
    )
    await _seed_invoice_with_line(
        db_session, org.id, customer.id, product=p,
        quantity=Decimal("1"), unit_price=Decimal("100.00"),
        status=InvoiceStatus.DRAFT,
    )

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/analytics/margins")
    body = r.json()
    assert float(body["overall"]["revenue"]) == 0.00
    assert body["top_products"] == []


async def test_margins_requires_pro_plan(db_session, two_orgs, client_factory):
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.FREE
    await db_session.commit()

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/analytics/margins")
    assert r.status_code in (402, 403)


async def test_margins_tenant_isolation(db_session, two_orgs, client_factory):
    """Org A must only see its own sales, not org B's."""
    org_a = two_orgs["a"]["org"]
    org_b = two_orgs["b"]["org"]
    org_a.plan = OrgPlan.PRO
    await db_session.commit()

    cust_b = await _seed_customer(db_session, org_b.id)
    p_b = await _seed_product(
        db_session, org_b.id, sku="B1", name="Only B",
        purchase=10, sell=100,
    )
    await _seed_invoice_with_line(
        db_session, org_b.id, cust_b.id, product=p_b,
        quantity=Decimal("100"), unit_price=Decimal("100.00"),
    )

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/analytics/margins")
    assert r.status_code == 200
    assert float(r.json()["overall"]["revenue"]) == 0.00
