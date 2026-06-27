"""Tests for /api/einvoice/peppol — Peppol BIS 3.0 XML export.

Covers:
- Swedish VAT format enforcement (422 on malformed, 200 on valid).
- Plan gate (FREE org → 403, PRO org → 200).
- XML structural requirements (namespaces, key UBL elements, invoice number).
- Cross-org isolation.

Requires a live PostgreSQL (see conftest._postgres_reachable).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.invoicing import Customer, Invoice, InvoiceLineItem, InvoiceStatus
from app.models.organization import OrgPlan




async def _seed_invoice(db, org_id):
    c = Customer(
        org_id=org_id,
        company_name="Peppol Kund AB",
        org_number="556111-2223",
        vat_number="SE556111222301",
        email="kund@example.com",
    )
    db.add(c)
    await db.flush()

    inv = Invoice(
        org_id=org_id,
        customer_id=c.id,
        invoice_number=f"INV-PPL-{str(c.id)[:4]}",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=30),
        status=InvoiceStatus.SENT,
        subtotal=Decimal("100.00"),
        vat_amount=Decimal("25.00"),
        total_sek=Decimal("125.00"),
    )
    db.add(inv)
    await db.flush()

    db.add(InvoiceLineItem(
        invoice_id=inv.id,
        description="Konsulttjänst",
        quantity=Decimal("1.000"),
        unit_price=Decimal("100.00"),
        tax_rate=Decimal("25.00"),
        line_total=Decimal("125.00"),
    ))
    await db.commit()
    await db.refresh(inv)
    return inv


async def test_peppol_export_requires_pro_plan(db_session, two_orgs, client_factory):
    """FREE org (default) must get 403 regardless of VAT format."""
    org = two_orgs["a"]["org"]
    org.vat_number = "SE556000000101"  # valid VAT — still blocked by plan gate
    await db_session.commit()

    inv = await _seed_invoice(db_session, org.id)

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.post(f"/api/einvoice/peppol/{inv.id}")
    assert r.status_code == 403


async def test_peppol_export_rejects_bad_swedish_vat(db_session, two_orgs, client_factory):
    """PRO org but malformed VAT → 422."""
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    org.vat_number = "SE123"  # too short
    await db_session.commit()

    inv = await _seed_invoice(db_session, org.id)

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.post(f"/api/einvoice/peppol/{inv.id}")
    assert r.status_code == 422
    assert "Swedish VAT" in r.json()["detail"]


async def test_peppol_export_rejects_missing_vat(db_session, two_orgs, client_factory):
    """PRO org with no VAT number at all → 422."""
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    org.vat_number = None
    await db_session.commit()

    inv = await _seed_invoice(db_session, org.id)

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.post(f"/api/einvoice/peppol/{inv.id}")
    assert r.status_code == 422


async def test_peppol_export_returns_valid_ubl_xml(db_session, two_orgs, client_factory):
    """Happy path: PRO + valid SE VAT → UBL 2.1 XML download."""
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    org.vat_number = "SE556000000101"
    await db_session.commit()

    inv = await _seed_invoice(db_session, org.id)

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.post(f"/api/einvoice/peppol/{inv.id}")

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/xml")
    assert f'filename="varuflow-invoice-{inv.invoice_number}.xml"' in r.headers["content-disposition"]

    body = r.text
    # UBL 2.1 / Peppol BIS 3.0 markers
    assert '<?xml version="1.0" encoding="UTF-8"?>' in body
    assert "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" in body
    assert "urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0" in body

    # Required aggregate elements
    assert "<cac:AccountingSupplierParty>" in body
    assert "<cac:AccountingCustomerParty>" in body
    assert "<cac:InvoiceLine>" in body
    assert "<cac:TaxTotal>" in body
    assert "<cac:LegalMonetaryTotal>" in body

    # Supplier VAT surfaces in the XML
    assert "SE556000000101" in body
    # Invoice id present
    assert inv.invoice_number in body


async def test_peppol_export_cross_org_isolation(db_session, two_orgs, client_factory):
    """Org A cannot export Org B's invoice — 404, never 403/422."""
    org_a = two_orgs["a"]["org"]
    org_b = two_orgs["b"]["org"]
    org_a.plan = OrgPlan.PRO
    org_a.vat_number = "SE556000000101"
    org_b.plan = OrgPlan.PRO
    org_b.vat_number = "SE556000000201"
    await db_session.commit()

    b_inv = await _seed_invoice(db_session, org_b.id)

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.post(f"/api/einvoice/peppol/{b_inv.id}")
    assert r.status_code == 404
