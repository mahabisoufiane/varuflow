"""Tests for dunning automation (v20)."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.dunning import DunningEvent
from app.models.invoicing import Customer, Invoice, InvoiceStatus
from app.services.dunning import run_dunning_sweep, stage_for_days_overdue




def test_stage_for_days_overdue_ladder():
    # Before any threshold
    assert stage_for_days_overdue(0, 0) is None
    assert stage_for_days_overdue(2, 0) is None

    # At each threshold
    assert stage_for_days_overdue(3, 0) == 1
    assert stage_for_days_overdue(7, 0) == 2
    assert stage_for_days_overdue(14, 0) == 3
    assert stage_for_days_overdue(30, 0) == 4

    # Between stages — should advance to highest reached
    assert stage_for_days_overdue(10, 0) == 2
    assert stage_for_days_overdue(20, 0) == 3
    assert stage_for_days_overdue(60, 0) == 4

    # Never re-emit already-sent stages
    assert stage_for_days_overdue(3, 1) is None
    assert stage_for_days_overdue(10, 2) is None
    assert stage_for_days_overdue(10, 1) == 2
    assert stage_for_days_overdue(45, 3) == 4


async def _seed_customer_and_invoice(
    db, org_id, *,
    days_past_due: int,
    stage: int = 0,
    total: Decimal = Decimal("1000.00"),
    email: str | None = "ar@customer.example",
) -> tuple[Customer, Invoice]:
    cust = Customer(
        org_id=org_id,
        company_name="Kundbolag AB",
        email=email,
    )
    db.add(cust)
    await db.flush()

    today = date.today()
    inv = Invoice(
        org_id=org_id,
        customer_id=cust.id,
        invoice_number=f"INV-{uuid.uuid4().hex[:8].upper()}",
        issue_date=today - timedelta(days=days_past_due + 30),
        due_date=today - timedelta(days=days_past_due),
        status=InvoiceStatus.SENT,
        subtotal=total,
        vat_amount=Decimal("0.00"),
        total_sek=total,
        dunning_stage=stage,
    )
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return cust, inv


async def test_sweep_emits_stage_1_at_day_3(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    _, inv = await _seed_customer_and_invoice(db_session, org.id, days_past_due=4)

    stats = await run_dunning_sweep(db_session)
    assert stats["scanned"] == 1
    assert stats["sent"] == 1
    assert stats["skipped"] == 0

    await db_session.refresh(inv)
    assert inv.dunning_stage == 1
    assert inv.last_dunning_sent_at is not None
    assert inv.status == InvoiceStatus.OVERDUE  # sweep bumps SENT → OVERDUE

    ev = (
        await db_session.execute(
            DunningEvent.__table__.select().where(DunningEvent.invoice_id == inv.id)
        )
    ).first()
    assert ev is not None
    assert ev.stage == 1
    assert ev.trigger == "scheduler"


async def test_sweep_is_idempotent(db_session, two_orgs):
    """Running the sweep twice the same day cannot double-send a stage."""
    org = two_orgs["a"]["org"]
    _, inv = await _seed_customer_and_invoice(db_session, org.id, days_past_due=8)

    stats1 = await run_dunning_sweep(db_session)
    stats2 = await run_dunning_sweep(db_session)
    assert stats1["sent"] == 1
    # Second run finds the stage already recorded → skips it (no new row)
    assert stats2["sent"] == 0

    rows = (
        await db_session.execute(
            DunningEvent.__table__.select().where(DunningEvent.invoice_id == inv.id)
        )
    ).all()
    assert len(rows) == 1


async def test_sweep_advances_through_stages(db_session, two_orgs):
    """Invoice at day +8 with stage=1 should advance to stage 2 only."""
    org = two_orgs["a"]["org"]
    _, inv = await _seed_customer_and_invoice(
        db_session, org.id, days_past_due=8, stage=1,
    )
    await run_dunning_sweep(db_session)

    await db_session.refresh(inv)
    assert inv.dunning_stage == 2
    rows = (
        await db_session.execute(
            DunningEvent.__table__.select().where(DunningEvent.invoice_id == inv.id)
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].stage == 2


async def test_sweep_skips_paid_invoices(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    _, inv = await _seed_customer_and_invoice(db_session, org.id, days_past_due=30)
    inv.status = InvoiceStatus.PAID
    await db_session.commit()

    stats = await run_dunning_sweep(db_session)
    assert stats["scanned"] == 0
    assert stats["sent"] == 0


async def test_sweep_skips_customer_without_email(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    _, inv = await _seed_customer_and_invoice(
        db_session, org.id, days_past_due=4, email=None,
    )
    stats = await run_dunning_sweep(db_session)
    assert stats["scanned"] == 1
    assert stats["skipped"] == 1
    await db_session.refresh(inv)
    assert inv.dunning_stage == 0  # no row recorded, stage unchanged


async def test_manual_send_reminder_endpoint(
    db_session, two_orgs, client_factory
):
    org = two_orgs["a"]["org"]
    _, inv = await _seed_customer_and_invoice(db_session, org.id, days_past_due=5)

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.post(f"/api/invoicing/invoices/{inv.id}/send-reminder")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stage"] == 1
    assert body["days_overdue"] == 5

    # Second manual call should 409 because the stage is already recorded
    # and no new stage is due (still only 5 days overdue).
    async with client_factory(two_orgs["a"]["member"]) as client:
        r2 = await client.post(f"/api/invoicing/invoices/{inv.id}/send-reminder")
    # 422 because the ladder won't advance at 5 days overdue past stage 1
    assert r2.status_code == 422


async def test_manual_send_reminder_rejects_not_overdue(
    db_session, two_orgs, client_factory
):
    org = two_orgs["a"]["org"]
    # Due today — no stage reached yet.
    _, inv = await _seed_customer_and_invoice(db_session, org.id, days_past_due=0)
    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.post(f"/api/invoicing/invoices/{inv.id}/send-reminder")
    assert r.status_code == 422


async def test_dunning_history_endpoint(db_session, two_orgs, client_factory):
    org = two_orgs["a"]["org"]
    _, inv = await _seed_customer_and_invoice(db_session, org.id, days_past_due=10)
    await run_dunning_sweep(db_session)

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get(f"/api/invoicing/invoices/{inv.id}/dunning-history")
    assert r.status_code == 200
    body = r.json()
    assert body["invoice_id"] == str(inv.id)
    assert len(body["events"]) == 1
    assert body["events"][0]["stage"] == 2  # 10 days overdue → stage 2


async def test_dunning_history_cross_org_404(db_session, two_orgs, client_factory):
    org_b = two_orgs["b"]["org"]
    _, inv_b = await _seed_customer_and_invoice(db_session, org_b.id, days_past_due=10)

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.get(f"/api/invoicing/invoices/{inv_b.id}/dunning-history")
    assert r.status_code == 404
