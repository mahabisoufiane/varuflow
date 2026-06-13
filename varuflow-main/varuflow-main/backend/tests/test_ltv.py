"""Tests for LTV / churn analytics (Feature 9)."""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.invoicing import (
    Customer,
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentMethod,
)
from app.models.organization import OrgPlan




async def _seed_customer(db, org_id, *, name="Kund AB") -> Customer:
    c = Customer(org_id=org_id, company_name=name, email=f"{uuid.uuid4().hex[:6]}@t.local")
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _seed_invoice(
    db, org_id, customer_id, *,
    total: Decimal,
    issue: date,
    status: InvoiceStatus = InvoiceStatus.SENT,
    paid_amount: Decimal | None = None,
) -> Invoice:
    inv = Invoice(
        org_id=org_id,
        customer_id=customer_id,
        invoice_number=f"INV-{uuid.uuid4().hex[:8].upper()}",
        issue_date=issue,
        due_date=issue + timedelta(days=30),
        status=status,
        subtotal=total,
        vat_amount=Decimal("0.00"),
        total_sek=total,
    )
    db.add(inv)
    await db.flush()
    if paid_amount is not None:
        db.add(Payment(
            org_id=org_id,
            invoice_id=inv.id,
            amount=paid_amount,
            payment_date=issue,
            method=PaymentMethod.BANK_TRANSFER,
        ))
    await db.commit()
    await db.refresh(inv)
    return inv


async def test_ltv_classifies_active_at_risk_churned(
    db_session, two_orgs, client_factory,
):
    """active = ≤60d, at_risk = 60-120d, churned = >120d."""
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()
    today = date.today()

    active = await _seed_customer(db_session, org.id, name="Active AB")
    at_risk = await _seed_customer(db_session, org.id, name="AtRisk AB")
    churned = await _seed_customer(db_session, org.id, name="Churned AB")

    await _seed_invoice(
        db_session, org.id, active.id,
        total=Decimal("1000.00"), issue=today - timedelta(days=10),
        paid_amount=Decimal("1000.00"),
    )
    await _seed_invoice(
        db_session, org.id, at_risk.id,
        total=Decimal("500.00"), issue=today - timedelta(days=90),
    )
    await _seed_invoice(
        db_session, org.id, churned.id,
        total=Decimal("2000.00"), issue=today - timedelta(days=200),
    )

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/analytics/ltv")
    assert r.status_code == 200, r.text
    body = r.json()

    summary = body["summary"]
    assert summary["total_customers"] == 3
    assert summary["active_customers"] == 1
    assert summary["at_risk_customers"] == 1
    assert summary["churned_customers"] == 1
    # churn_rate = 1/3 ≈ 33.33
    assert 33.0 <= summary["churn_rate_pct"] <= 33.5

    by_name = {c["company_name"]: c for c in body["top_customers"]}
    assert by_name["Active AB"]["status"] == "active"
    assert by_name["AtRisk AB"]["status"] == "at_risk"
    assert by_name["Churned AB"]["status"] == "churned"
    # Active customer's paid amount tracked via Payment table
    assert float(by_name["Active AB"]["total_paid"]) == 1000.00
    assert float(by_name["AtRisk AB"]["total_paid"]) == 0.00


async def test_ltv_avg_median_and_ranking(
    db_session, two_orgs, client_factory,
):
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()
    today = date.today()

    totals = [Decimal("100"), Decimal("500"), Decimal("900")]
    for i, t in enumerate(totals):
        c = await _seed_customer(db_session, org.id, name=f"Customer {i}")
        await _seed_invoice(
            db_session, org.id, c.id,
            total=t, issue=today - timedelta(days=5),
        )

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/analytics/ltv")
    assert r.status_code == 200
    body = r.json()
    # avg = 500, median = 500
    assert float(body["summary"]["avg_ltv"]) == 500.00
    assert float(body["summary"]["median_ltv"]) == 500.00
    # top ranked by total_invoiced desc
    assert body["top_customers"][0]["company_name"] == "Customer 2"
    assert float(body["top_customers"][0]["total_invoiced"]) == 900.00


async def test_ltv_excludes_draft_invoices(
    db_session, two_orgs, client_factory,
):
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()
    today = date.today()

    c = await _seed_customer(db_session, org.id)
    await _seed_invoice(
        db_session, org.id, c.id,
        total=Decimal("999.00"), issue=today - timedelta(days=5),
        status=InvoiceStatus.DRAFT,
    )

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/analytics/ltv")
    assert r.status_code == 200
    body = r.json()
    # Draft-only customer has no qualifying invoices and so doesn't appear.
    assert body["summary"]["total_customers"] == 0


async def test_ltv_cohorts_group_by_first_invoice_month(
    db_session, two_orgs, client_factory,
):
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()

    # Two customers whose first invoice is in the same month.
    cohort_month = date(2025, 3, 10)
    for name in ["C1", "C2"]:
        c = await _seed_customer(db_session, org.id, name=name)
        await _seed_invoice(
            db_session, org.id, c.id,
            total=Decimal("250.00"), issue=cohort_month,
        )

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/analytics/ltv")
    assert r.status_code == 200
    body = r.json()
    months = {c["cohort_month"]: c for c in body["cohorts"]}
    assert "2025-03" in months
    assert months["2025-03"]["customers"] == 2
    assert float(months["2025-03"]["total_revenue"]) == 500.00
    assert float(months["2025-03"]["avg_ltv"]) == 250.00


async def test_ltv_requires_pro_plan(
    db_session, two_orgs, client_factory,
):
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.FREE
    await db_session.commit()

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/analytics/ltv")
    assert r.status_code in (402, 403)


async def test_ltv_tenant_isolation(
    db_session, two_orgs, client_factory,
):
    """Org A must not see Org B's customers/invoices."""
    org_a = two_orgs["a"]["org"]
    org_b = two_orgs["b"]["org"]
    org_a.plan = OrgPlan.PRO
    org_b.plan = OrgPlan.PRO
    await db_session.commit()
    today = date.today()

    c_b = await _seed_customer(db_session, org_b.id, name="OrgB Client")
    await _seed_invoice(
        db_session, org_b.id, c_b.id,
        total=Decimal("9999.00"), issue=today - timedelta(days=5),
    )

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get("/api/analytics/ltv")
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]["total_customers"] == 0
    assert body["top_customers"] == []
