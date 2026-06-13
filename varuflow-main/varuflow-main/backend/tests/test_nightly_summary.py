"""Tests for Item 21 — Nightly business summary email."""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.audit import AuditLogEntry
from app.models.invoicing import Customer, Invoice, InvoiceStatus
from app.models.inventory import Product, StockLevel, Warehouse
from app.models.organization import Organization
from app.services.nightly_summary import (
    SummaryStats,
    _pick_insight,
    build_summary_stats,
    render_summary_html,
    run_summary_for_org,
)




# ─────────────────────────────────────────────────────────────────────────────
# Pure-function tests (no DB)
# ─────────────────────────────────────────────────────────────────────────────

def test_insight_prioritises_overdue():
    s = SummaryStats(
        date=date(2026, 4, 22),
        overdue_count=3,
        overdue_total=Decimal("12500"),
        low_stock_count=10,
    )
    assert "overdue" in _pick_insight(s).lower()


def test_insight_falls_through_to_low_stock():
    s = SummaryStats(date=date(2026, 4, 22), low_stock_count=7)
    assert "reorder" in _pick_insight(s).lower()


def test_insight_revenue_drop():
    s = SummaryStats(
        date=date(2026, 4, 22),
        revenue=Decimal("80"),
        revenue_prev=Decimal("200"),
        revenue_delta_pct=Decimal("-60.0"),
    )
    assert "dropped" in _pick_insight(s).lower()


def test_insight_steady_default():
    s = SummaryStats(date=date(2026, 4, 22), orders_count=3)
    assert "steady" in _pick_insight(s).lower()


def test_insight_no_orders():
    s = SummaryStats(date=date(2026, 4, 22), orders_count=0)
    assert "no orders" in _pick_insight(s).lower()


def test_render_escapes_org_name():
    s = SummaryStats(date=date(2026, 4, 22), revenue=Decimal("100"))
    # XSS attempt in org name must be HTML-escaped, not rendered.
    html = render_summary_html("<script>alert(1)</script>", s)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


# ─────────────────────────────────────────────────────────────────────────────
# DB-backed tests
# ─────────────────────────────────────────────────────────────────────────────

async def _seed_product(db, org_id, *, reorder=5):
    wh = Warehouse(org_id=org_id, name="NS-WH")
    db.add(wh)
    p = Product(
        org_id=org_id,
        name="Thing",
        sku=f"NS-{uuid.uuid4().hex[:6]}",
        unit="st",
        purchase_price=Decimal("5"),
        sell_price=Decimal("10"),
        reorder_level=reorder,
    )
    db.add(p)
    await db.flush()
    return p, wh


async def _seed_invoice(
    db, org_id, customer_id, *, issue: date, due: date,
    total: Decimal, status: InvoiceStatus = InvoiceStatus.SENT,
):
    inv = Invoice(
        org_id=org_id,
        customer_id=customer_id,
        invoice_number=f"INV-{uuid.uuid4().hex[:8]}",
        issue_date=issue,
        due_date=due,
        status=status,
        subtotal=total,
        total_sek=total,
    )
    db.add(inv)
    await db.flush()
    return inv


async def _seed_customer(db, org_id):
    c = Customer(org_id=org_id, name=f"Cust-{uuid.uuid4().hex[:4]}")
    db.add(c)
    await db.flush()
    return c


async def test_build_summary_counts_invoices_and_overdue(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    customer = await _seed_customer(db_session, org.id)
    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)

    # Invoice issued yesterday, paid status — still counts toward
    # "issued yesterday" revenue (status != DRAFT).
    await _seed_invoice(
        db_session, org.id, customer.id,
        issue=yesterday, due=yesterday + timedelta(days=30),
        total=Decimal("1000"),
        status=InvoiceStatus.SENT,
    )
    # Overdue invoice from earlier.
    await _seed_invoice(
        db_session, org.id, customer.id,
        issue=today - timedelta(days=15),
        due=today - timedelta(days=5),
        total=Decimal("500"),
        status=InvoiceStatus.SENT,
    )
    # DRAFT invoice should NOT show up anywhere.
    await _seed_invoice(
        db_session, org.id, customer.id,
        issue=yesterday, due=today + timedelta(days=10),
        total=Decimal("99999"),
        status=InvoiceStatus.DRAFT,
    )
    await db_session.commit()

    stats = await build_summary_stats(db_session, org.id)
    assert stats.date == yesterday
    assert stats.revenue == Decimal("1000")
    assert stats.invoices_count == 1
    assert stats.orders_count == 1  # no POS sales seeded
    assert stats.overdue_count == 1
    assert stats.overdue_total == Decimal("500")
    assert stats.ai_insight  # something populated


async def test_build_summary_low_stock_uses_reorder_level(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    # Product with reorder_level=5, zero stock → should count.
    p, wh = await _seed_product(db_session, org.id, reorder=5)
    db_session.add(StockLevel(org_id=org.id, product_id=p.id, warehouse_id=wh.id, quantity=0))
    # Second product well-stocked → must not count.
    p2, wh2 = await _seed_product(db_session, org.id, reorder=3)
    db_session.add(StockLevel(org_id=org.id, product_id=p2.id, warehouse_id=wh2.id, quantity=50))
    await db_session.commit()

    stats = await build_summary_stats(db_session, org.id)
    assert stats.low_stock_count == 1


async def test_run_summary_sends_and_audits(db_session, two_orgs):
    org = two_orgs["a"]["org"]

    with patch(
        "app.services.nightly_summary.send_summary_email",
        new=AsyncMock(return_value=True),
    ) as mock_send:
        result = await run_summary_for_org(
            db_session, org, to_email="owner@example.com",
        )
    await db_session.commit()

    assert result.sent is True
    assert result.reason == "sent"
    mock_send.assert_awaited_once()

    entries = (
        await db_session.execute(
            select(AuditLogEntry).where(
                AuditLogEntry.org_id == org.id,
                AuditLogEntry.action == "NIGHTLY_SUMMARY_SENT",
            )
        )
    ).scalars().all()
    assert len(entries) == 1
    assert entries[0].extra["to"] == "owner@example.com"
    # Summary numeric fields survive the audit round-trip.
    assert "revenue" in entries[0].extra


async def test_run_summary_resend_failure_logs_failed(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    with patch(
        "app.services.nightly_summary.send_summary_email",
        new=AsyncMock(return_value=False),
    ):
        result = await run_summary_for_org(
            db_session, org, to_email="owner@example.com",
        )
    await db_session.commit()

    assert result.sent is False
    assert result.reason == "resend_failed"
    entries = (
        await db_session.execute(
            select(AuditLogEntry).where(
                AuditLogEntry.org_id == org.id,
                AuditLogEntry.action == "NIGHTLY_SUMMARY_FAILED",
            )
        )
    ).scalars().all()
    assert len(entries) == 1
    assert entries[0].extra["reason"] == "resend_failed"


async def test_run_summary_no_email_skips_send(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    with patch(
        "app.services.nightly_summary.send_summary_email",
        new=AsyncMock(return_value=True),
    ) as mock_send:
        result = await run_summary_for_org(db_session, org, to_email=None)
    await db_session.commit()

    mock_send.assert_not_awaited()
    assert result.sent is False
    assert result.reason == "no_email"
    entries = (
        await db_session.execute(
            select(AuditLogEntry).where(
                AuditLogEntry.org_id == org.id,
                AuditLogEntry.action == "NIGHTLY_SUMMARY_FAILED",
            )
        )
    ).scalars().all()
    assert len(entries) == 1
    assert entries[0].extra["reason"] == "no_email"


async def test_run_summary_is_idempotent_within_day(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    with patch(
        "app.services.nightly_summary.send_summary_email",
        new=AsyncMock(return_value=True),
    ) as mock_send:
        first = await run_summary_for_org(db_session, org, to_email="o@x.com")
        await db_session.commit()
        second = await run_summary_for_org(db_session, org, to_email="o@x.com")
        await db_session.commit()

    assert first.sent is True
    assert second.sent is False
    assert second.reason == "already_sent_today"
    # Second call must NOT re-hit Resend.
    mock_send.assert_awaited_once()


# ─────────────────────────────────────────────────────────────────────────────
# Settings endpoint
# ─────────────────────────────────────────────────────────────────────────────

async def test_update_nightly_summary_settings_requires_owner(
    db_session, two_orgs, client_factory,
):
    # OrganizationMember role is OWNER by default in the fixture so we
    # just verify the happy path + time snapping.
    member = two_orgs["a"]["member"]
    async with client_factory(member) as client:
        r = await client.put(
            "/api/notifications/nightly-summary",
            json={"enabled": True, "time": "07:23"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enabled"] is True
    # 07:23 → 07:15 (15-min grid, floored)
    assert body["time"] == "07:15"


async def test_update_nightly_summary_rejects_bad_time(
    db_session, two_orgs, client_factory,
):
    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.put(
            "/api/notifications/nightly-summary",
            json={"time": "99:99"},
        )
    assert r.status_code == 400
