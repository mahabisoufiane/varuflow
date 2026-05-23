"""Tests for POST /api/gdpr/bokforing-export.

Covers:
- Non-owner (member / admin) → 403.
- Owner happy path → 200, ZIP bytes containing audit_log.csv + ledger.json.
- Smoke-test entry for auth requirement is in test_endpoints_smoke.py.

Requires a live PostgreSQL (see conftest._postgres_reachable).
"""
from __future__ import annotations

import io
import json
import zipfile
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.invoicing import Customer, Invoice, InvoiceLineItem, InvoiceStatus
from app.models.organization import OrgRole




async def _seed_invoice(db, org_id):
    c = Customer(org_id=org_id, company_name="Bokföring Kund AB", email="k@example.com")
    db.add(c)
    await db.flush()
    inv = Invoice(
        org_id=org_id,
        customer_id=c.id,
        invoice_number=f"INV-BF-{str(c.id)[:4]}",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=30),
        status=InvoiceStatus.SENT,
        subtotal=Decimal("200.00"),
        vat_amount=Decimal("50.00"),
        total_sek=Decimal("250.00"),
    )
    db.add(inv)
    await db.flush()
    db.add(InvoiceLineItem(
        invoice_id=inv.id,
        description="Test",
        quantity=Decimal("1.000"),
        unit_price=Decimal("200.00"),
        tax_rate=Decimal("25.00"),
        line_total=Decimal("250.00"),
    ))
    await db.commit()
    await db.refresh(inv)
    return inv


async def test_bokforing_export_rejects_non_owner(db_session, two_orgs, client_factory):
    """A plain MEMBER cannot run the compliance export."""
    member = two_orgs["a"]["member"]
    member.role = OrgRole.MEMBER
    await db_session.commit()

    async with client_factory(member) as client:
        r = await client.post("/api/gdpr/bokforing-export")
    assert r.status_code == 403


async def test_bokforing_export_owner_returns_zip(db_session, two_orgs, client_factory):
    """Owner gets a well-formed ZIP with the three required artefacts."""
    org = two_orgs["a"]["org"]
    member = two_orgs["a"]["member"]
    assert member.role == OrgRole.OWNER  # fixture default

    inv = await _seed_invoice(db_session, org.id)

    async with client_factory(member) as client:
        r = await client.post("/api/gdpr/bokforing-export")

    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    assert f"varuflow-bokforing-{org.id}-" in r.headers["content-disposition"]

    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        names = zf.namelist()
        assert "audit_log.csv" in names
        assert "ledger.json" in names
        assert "README.txt" in names
        # At least one invoice PDF
        assert any(n.startswith("invoices/") and n.endswith(".pdf") for n in names)

        ledger = json.loads(zf.read("ledger.json").decode("utf-8"))
        assert isinstance(ledger, list)
        assert any(entry["invoice_number"] == inv.invoice_number for entry in ledger)
        sample = next(e for e in ledger if e["invoice_number"] == inv.invoice_number)
        assert sample["currency"] == "SEK"
        assert sample["customer_name"] == "Bokföring Kund AB"
        assert sample["status"] == "SENT"
