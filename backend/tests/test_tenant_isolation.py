"""Multi-tenant isolation integration tests.

CLAUDE.md Rule 2 — "Every data query MUST filter by org_id — users must
never see another org's data." These tests exercise that guarantee by
creating two organizations, seeding data for each, and asserting that
endpoints called as Org A never return Org B's rows.

Requires a live PostgreSQL. Skipped automatically when the DB is
unreachable (see conftest._postgres_reachable).
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models.invoicing import Customer, Invoice, InvoiceLineItem, InvoiceStatus




async def _seed_customer(db, org_id, name: str) -> Customer:
    c = Customer(org_id=org_id, company_name=name, email=f"{name.lower()}@example.com")
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _seed_invoice(db, org_id, customer_id, number: str) -> Invoice:
    inv = Invoice(
        org_id=org_id,
        customer_id=customer_id,
        invoice_number=number,
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=30),
        status=InvoiceStatus.SENT,
    )
    db.add(inv)
    await db.flush()
    db.add(InvoiceLineItem(
        invoice_id=inv.id,
        description="Test item",
        quantity=1,
        unit_price=100,
        tax_rate=25,
        line_total=125,
    ))
    await db.commit()
    await db.refresh(inv)
    return inv


async def test_customers_list_isolated(db_session, two_orgs, client_factory):
    await _seed_customer(db_session, two_orgs["a"]["org"].id, "AlphaCustomer")
    await _seed_customer(db_session, two_orgs["b"]["org"].id, "BravoCustomer")

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/invoicing/customers")
    assert r.status_code == 200
    names = [c["company_name"] for c in r.json()]
    assert "AlphaCustomer" in names
    assert "BravoCustomer" not in names


async def test_customer_detail_cross_org_returns_404(db_session, two_orgs, client_factory):
    b_customer = await _seed_customer(db_session, two_orgs["b"]["org"].id, "BravoOnly")

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get(f"/api/invoicing/customers/{b_customer.id}")
    assert r.status_code == 404


async def test_invoices_list_isolated(db_session, two_orgs, client_factory):
    a_customer = await _seed_customer(db_session, two_orgs["a"]["org"].id, "AlphaCust")
    b_customer = await _seed_customer(db_session, two_orgs["b"]["org"].id, "BravoCust")
    await _seed_invoice(db_session, two_orgs["a"]["org"].id, a_customer.id, "INV-A-1")
    await _seed_invoice(db_session, two_orgs["b"]["org"].id, b_customer.id, "INV-B-1")

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/invoicing/invoices")
    assert r.status_code == 200
    numbers = [inv["invoice_number"] for inv in r.json()]
    assert "INV-A-1" in numbers
    assert "INV-B-1" not in numbers


async def test_invoice_detail_cross_org_returns_404(db_session, two_orgs, client_factory):
    b_customer = await _seed_customer(db_session, two_orgs["b"]["org"].id, "BravoOnly2")
    b_invoice  = await _seed_invoice(db_session, two_orgs["b"]["org"].id, b_customer.id, "INV-B-2")

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get(f"/api/invoicing/invoices/{b_invoice.id}")
    assert r.status_code == 404


async def test_cannot_create_invoice_for_other_orgs_customer(db_session, two_orgs, client_factory):
    b_customer = await _seed_customer(db_session, two_orgs["b"]["org"].id, "BravoCust3")

    body = {
        "customer_id": str(b_customer.id),
        "issue_date": date.today().isoformat(),
        "due_date": (date.today() + timedelta(days=30)).isoformat(),
        "items": [{"description": "x", "quantity": 1, "unit_price": 10, "tax_rate": 25}],
    }
    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.post("/api/invoicing/invoices", json=body)
    # Router explicitly 404s on a cross-org customer
    assert r.status_code == 404


async def test_gdpr_export_only_dumps_own_org(db_session, two_orgs, client_factory):
    a_customer = await _seed_customer(db_session, two_orgs["a"]["org"].id, "AlphaPrivate")
    b_customer = await _seed_customer(db_session, two_orgs["b"]["org"].id, "BravoPrivate")

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/gdpr/export")
    assert r.status_code == 200
    dump = r.json()
    names = [c["company_name"] for c in dump["customers"]]
    assert "AlphaPrivate" in names
    assert "BravoPrivate" not in names
    # Organization block must be Org A's, not B's
    assert dump["organization"]["id"] == str(two_orgs["a"]["org"].id)
