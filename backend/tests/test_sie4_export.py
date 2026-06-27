"""Tests for POST /api/accounting/sie4-export.

Covers:
- Non-owner is rejected (403).
- Owner happy path: 3 invoices → correct #VER count + balanced #TRANS
  lines per verification + required SIE headers present.
- Filename + content-type match the spec.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.models.invoicing import Customer, Invoice, InvoiceStatus
from app.models.organization import OrgRole



async def _seed(db, org_id, n=3, *, status=InvoiceStatus.SENT, year=2025):
    cust = Customer(org_id=org_id, company_name="SIE Kund AB", email="sie@example.com")
    db.add(cust)
    await db.flush()
    invs = []
    for i in range(1, n + 1):
        inv = Invoice(
            org_id=org_id,
            customer_id=cust.id,
            invoice_number=f"INV-SIE-{i:04d}",
            issue_date=date(year, 3, i + 1),
            due_date=date(year, 4, i + 1),
            status=status,
            subtotal=Decimal("100.00"),
            vat_amount=Decimal("25.00"),
            total_sek=Decimal("125.00"),
        )
        db.add(inv)
        invs.append(inv)
    await db.commit()
    return invs


async def test_sie4_export_rejects_non_owner(db_session, two_orgs, client_factory):
    member = two_orgs["a"]["member"]
    member.role = OrgRole.MEMBER
    await db_session.commit()

    async with client_factory(member) as client:
        r = await client.post("/api/accounting/sie4-export?year=2025")
    assert r.status_code == 403


async def test_sie4_export_three_invoices_balanced(db_session, two_orgs, client_factory):
    org = two_orgs["a"]["org"]
    org.org_number = "556000-0001"
    member = two_orgs["a"]["member"]
    assert member.role == OrgRole.OWNER
    await db_session.commit()

    await _seed(db_session, org.id, n=3, year=2025)
    # A DRAFT invoice in the same year must NOT appear in the export.
    await _seed(db_session, org.id, n=1, status=InvoiceStatus.DRAFT, year=2025)
    # An out-of-year invoice must also be excluded.
    await _seed(db_session, org.id, n=1, year=2024)

    async with client_factory(member) as client:
        r = await client.post("/api/accounting/sie4-export?year=2025")

    assert r.status_code == 200, r.text
    assert r.headers["content-disposition"].endswith('filename="varuflow-SIE4-2025.se"')
    assert r.headers["content-type"].startswith("text/plain")

    body = r.content.decode("cp437")

    # Required SIE4 headers
    assert "#FLAGGA 0" in body
    assert "#PROGRAM " in body
    assert "#FORMAT PC8" in body
    assert "#GEN " in body
    assert "#ORGNR 556000-0001" in body
    assert "#FNAMN " in body
    # Three required chart-of-account entries
    assert "#KONTO 1510 " in body
    assert "#KONTO 2610 " in body
    assert "#KONTO 3000 " in body

    # Exactly three #VER — DRAFT and out-of-year must be filtered out.
    ver_lines = [ln for ln in body.splitlines() if ln.startswith("#VER ")]
    assert len(ver_lines) == 3

    # Each #VER block must contain 3 #TRANS lines that sum to zero.
    blocks = body.split("#VER ")[1:]
    for block in blocks:
        trans = [ln.strip() for ln in block.splitlines() if ln.strip().startswith("#TRANS")]
        assert len(trans) == 3
        total = Decimal("0.00")
        for ln in trans:
            # #TRANS 1510 {} 125.00
            amount = Decimal(ln.split()[-1])
            total += amount
        assert total == Decimal("0.00"), f"unbalanced verification: {total}"
