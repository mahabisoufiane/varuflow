"""Tests for recurring invoice auto-send (Item 17 — v39).

Covers the service entry point ``auto_send_invoice`` and the
end-to-end path through ``POST /api/recurring/{id}/run``:

* Schedule with ``auto_send`` disabled leaves the generated invoice in
  DRAFT and emits no audit event.
* Schedule with ``auto_send`` enabled and email configured delivers via
  Resend and flips DRAFT → SENT.
* Peppol channel fires only when the customer has ``peppol_enabled``
  AND a ``peppol_id``; otherwise it short-circuits with a reason.
* Both channels can be attempted in the same run; partial success still
  flips the invoice to SENT.
* Transport failure leaves the invoice in place (DRAFT) and emits a
  failed audit event — the spec is explicit that we never roll the
  generated invoice back on send failure.
* Audit events distinguish success from failure via the ``action`` field
  (``recurring_invoice.auto_sent`` vs ``.auto_send_failed``).
* PATCH ``/settings`` updates auto-send configuration and writes an
  audit trail of the before/after change.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.audit import AuditLogEntry
from app.models.invoicing import (
    Customer,
    Invoice,
    InvoiceLineItem,
    InvoiceStatus,
    RecurringFrequency,
    RecurringInvoice,
)
from app.models.organization import OrgPlan
from app.services.recurring_send import (
    _parse_methods,
    auto_send_invoice,
    generate_invoice_from_recurring,
)




async def _seed_schedule(
    db,
    org_id,
    *,
    auto_send: bool = False,
    auto_send_method: str = "email",
    customer_email: str | None = "ar@customer.example",
    peppol_enabled: bool = False,
    peppol_id: str | None = None,
    customer_active: bool = True,
) -> tuple[Customer, Invoice, RecurringInvoice]:
    """Seed a complete schedule: customer + template invoice + recurring row.

    The template has one line item so generation exercises the full
    clone path (line-item cascade, totals, tax_rate).
    """
    cust = Customer(
        org_id=org_id,
        company_name="Auto Kundbolag AB",
        email=customer_email,
        payment_terms_days=30,
        is_active=customer_active,
        peppol_enabled=peppol_enabled,
        peppol_id=peppol_id,
    )
    db.add(cust)
    await db.flush()

    tmpl = Invoice(
        org_id=org_id,
        customer_id=cust.id,
        invoice_number=f"INV-TMPL-{uuid.uuid4().hex[:6].upper()}",
        issue_date=date.today() - timedelta(days=30),
        due_date=date.today(),
        status=InvoiceStatus.SENT,
        subtotal=Decimal("800.00"),
        vat_amount=Decimal("200.00"),
        total_sek=Decimal("1000.00"),
        line_items=[
            InvoiceLineItem(
                description="Monthly retainer",
                quantity=Decimal("1.000"),
                unit_price=Decimal("800.00"),
                tax_rate=Decimal("25.00"),
                line_total=Decimal("800.00"),
            )
        ],
    )
    db.add(tmpl)
    await db.flush()

    rec = RecurringInvoice(
        org_id=org_id,
        customer_id=cust.id,
        frequency=RecurringFrequency.MONTHLY,
        next_run_date=date.today(),
        template_invoice_id=tmpl.id,
        is_active=True,
        auto_send=auto_send,
        auto_send_method=auto_send_method,
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return cust, tmpl, rec


# ─────────────────────────────────────────────────────────────────────────────
# Pure unit tests — no DB
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_methods_accepts_both_channels():
    assert _parse_methods("email") == ["email"]
    assert _parse_methods("peppol") == ["peppol"]
    assert _parse_methods("email,peppol") == ["email", "peppol"]
    assert _parse_methods(" email , peppol ") == ["email", "peppol"]


def test_parse_methods_drops_unknown_and_empty():
    # Unknown channels are silently dropped so a typo on a legacy row
    # cannot poison the sweep.
    assert _parse_methods("email,sms") == ["email"]
    assert _parse_methods("") == []
    assert _parse_methods(None) == []
    assert _parse_methods("bogus") == []


# ─────────────────────────────────────────────────────────────────────────────
# Generation helper
# ─────────────────────────────────────────────────────────────────────────────


async def test_generate_produces_draft_and_advances_date(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    _, _, rec = await _seed_schedule(db_session, org.id)
    before = rec.next_run_date

    new_inv = await generate_invoice_from_recurring(
        db_session, recurring=rec, org_id=org.id
    )
    await db_session.commit()

    assert new_inv.status == InvoiceStatus.DRAFT
    assert new_inv.invoice_number.startswith("INV-")
    assert new_inv.org_id == org.id
    assert len(new_inv.line_items) == 1
    # Advance exactly one month (day preserved unless target shorter).
    await db_session.refresh(rec)
    assert rec.next_run_date > before


# ─────────────────────────────────────────────────────────────────────────────
# auto_send_invoice — direct service calls
# ─────────────────────────────────────────────────────────────────────────────


async def test_auto_send_disabled_does_nothing(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    _, _, rec = await _seed_schedule(
        db_session, org.id, auto_send=False, auto_send_method="email"
    )
    new_inv = await generate_invoice_from_recurring(
        db_session, recurring=rec, org_id=org.id
    )
    await db_session.commit()

    result = await auto_send_invoice(
        db_session, recurring=rec, invoice_id=new_inv.id
    )

    assert result.channels_attempted == []
    assert not result.success
    await db_session.refresh(new_inv)
    assert new_inv.status == InvoiceStatus.DRAFT

    # No audit event fired for a disabled schedule.
    audits = (
        await db_session.execute(
            select(AuditLogEntry).where(
                AuditLogEntry.target_id == str(new_inv.id)
            )
        )
    ).scalars().all()
    assert audits == []


async def test_auto_send_email_success_flips_to_sent(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    _, _, rec = await _seed_schedule(
        db_session, org.id, auto_send=True, auto_send_method="email"
    )
    new_inv = await generate_invoice_from_recurring(
        db_session, recurring=rec, org_id=org.id
    )
    await db_session.commit()

    with patch(
        "app.services.recurring_send.send_invoice_email",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.routers.invoicing._generate_invoice_pdf", return_value=b"%PDF-fake"
    ):
        result = await auto_send_invoice(
            db_session, recurring=rec, invoice_id=new_inv.id
        )

    assert result.success
    assert "email" in result.channels_succeeded
    await db_session.refresh(new_inv)
    assert new_inv.status == InvoiceStatus.SENT

    actions = (
        await db_session.execute(
            select(AuditLogEntry.action).where(
                AuditLogEntry.target_id == str(new_inv.id)
            )
        )
    ).scalars().all()
    assert "recurring_invoice.auto_sent" in actions


async def test_auto_send_email_failure_keeps_invoice(db_session, two_orgs):
    """Resend returns False (or not configured) — invoice stays DRAFT
    and a failure audit event is written. No exception bubbles up.
    """
    org = two_orgs["a"]["org"]
    _, _, rec = await _seed_schedule(
        db_session, org.id, auto_send=True, auto_send_method="email"
    )
    new_inv = await generate_invoice_from_recurring(
        db_session, recurring=rec, org_id=org.id
    )
    await db_session.commit()

    with patch(
        "app.services.recurring_send.send_invoice_email",
        new=AsyncMock(return_value=False),
    ), patch(
        "app.routers.invoicing._generate_invoice_pdf", return_value=b"%PDF-fake"
    ):
        result = await auto_send_invoice(
            db_session, recurring=rec, invoice_id=new_inv.id
        )

    assert not result.success
    assert "email" in result.channels_failed
    await db_session.refresh(new_inv)
    assert new_inv.status == InvoiceStatus.DRAFT  # unchanged

    actions = (
        await db_session.execute(
            select(AuditLogEntry.action).where(
                AuditLogEntry.target_id == str(new_inv.id)
            )
        )
    ).scalars().all()
    assert "recurring_invoice.auto_send_failed" in actions


async def test_auto_send_email_skipped_without_customer_email(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    _, _, rec = await _seed_schedule(
        db_session,
        org.id,
        auto_send=True,
        auto_send_method="email",
        customer_email=None,
    )
    new_inv = await generate_invoice_from_recurring(
        db_session, recurring=rec, org_id=org.id
    )
    await db_session.commit()

    result = await auto_send_invoice(
        db_session, recurring=rec, invoice_id=new_inv.id
    )

    assert not result.success
    assert result.errors.get("email") == "customer_has_no_email"


async def test_auto_send_peppol_skipped_when_not_enabled(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    _, _, rec = await _seed_schedule(
        db_session,
        org.id,
        auto_send=True,
        auto_send_method="peppol",
        peppol_enabled=False,
    )
    new_inv = await generate_invoice_from_recurring(
        db_session, recurring=rec, org_id=org.id
    )
    await db_session.commit()

    result = await auto_send_invoice(
        db_session, recurring=rec, invoice_id=new_inv.id
    )
    assert not result.success
    assert result.errors.get("peppol") == "peppol_not_enabled_on_customer"


async def test_auto_send_peppol_success_when_configured(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    _, _, rec = await _seed_schedule(
        db_session,
        org.id,
        auto_send=True,
        auto_send_method="peppol",
        peppol_enabled=True,
        peppol_id="0007:5560000001",
    )
    new_inv = await generate_invoice_from_recurring(
        db_session, recurring=rec, org_id=org.id
    )
    await db_session.commit()

    with patch(
        "app.routers.invoicing._generate_peppol_xml",
        return_value=b"<Invoice/>",
    ):
        result = await auto_send_invoice(
            db_session, recurring=rec, invoice_id=new_inv.id
        )

    assert result.success
    assert "peppol" in result.channels_succeeded
    await db_session.refresh(new_inv)
    assert new_inv.status == InvoiceStatus.SENT


async def test_auto_send_both_channels_partial_success(db_session, two_orgs):
    """Email succeeds, Peppol not configured — invoice flips to SENT
    but the failure is still recorded per-channel. The spec calls out
    that a partial success is still considered a send."""
    org = two_orgs["a"]["org"]
    _, _, rec = await _seed_schedule(
        db_session,
        org.id,
        auto_send=True,
        auto_send_method="email,peppol",
        peppol_enabled=False,
    )
    new_inv = await generate_invoice_from_recurring(
        db_session, recurring=rec, org_id=org.id
    )
    await db_session.commit()

    with patch(
        "app.services.recurring_send.send_invoice_email",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.routers.invoicing._generate_invoice_pdf", return_value=b"%PDF-fake"
    ):
        result = await auto_send_invoice(
            db_session, recurring=rec, invoice_id=new_inv.id
        )

    assert result.success
    assert "email" in result.channels_succeeded
    assert "peppol" in result.channels_failed
    await db_session.refresh(new_inv)
    assert new_inv.status == InvoiceStatus.SENT


# ─────────────────────────────────────────────────────────────────────────────
# HTTP round-trip through POST /api/recurring/{id}/run
# ─────────────────────────────────────────────────────────────────────────────


async def test_run_now_autosends_when_enabled(db_session, two_orgs, client_factory):
    org = two_orgs["a"]["org"]
    # Plan gate — recurring routes require PRO.
    org.plan = OrgPlan.PRO
    await db_session.commit()

    _, _, rec = await _seed_schedule(
        db_session, org.id, auto_send=True, auto_send_method="email"
    )

    with patch(
        "app.services.recurring_send.send_invoice_email",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.routers.invoicing._generate_invoice_pdf", return_value=b"%PDF-fake"
    ):
        async with client_factory(two_orgs["a"]["member"]) as client:
            r = await client.post(f"/api/recurring/{rec.id}/run")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "created"
    assert body["auto_send"]["succeeded"] == ["email"]


async def test_run_now_without_autosend_returns_draft(
    db_session, two_orgs, client_factory
):
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()

    _, _, rec = await _seed_schedule(db_session, org.id, auto_send=False)

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.post(f"/api/recurring/{rec.id}/run")
    assert r.status_code == 201
    body = r.json()
    assert body["auto_send"] is None


async def test_patch_settings_updates_auto_send(
    db_session, two_orgs, client_factory
):
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()

    _, _, rec = await _seed_schedule(
        db_session, org.id, auto_send=False, auto_send_method="email"
    )

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.patch(
            f"/api/recurring/{rec.id}/settings",
            json={"auto_send": True, "auto_send_method": "email,peppol"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["auto_send"] is True
    assert body["auto_send_method"] == "email,peppol"

    # Audit entry recorded the change.
    actions = (
        await db_session.execute(
            select(AuditLogEntry.action).where(
                AuditLogEntry.target_id == str(rec.id)
            )
        )
    ).scalars().all()
    assert "recurring_invoice.settings_updated" in actions


async def test_patch_settings_rejects_unknown_method(
    db_session, two_orgs, client_factory
):
    org = two_orgs["a"]["org"]
    org.plan = OrgPlan.PRO
    await db_session.commit()

    _, _, rec = await _seed_schedule(db_session, org.id)

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.patch(
            f"/api/recurring/{rec.id}/settings",
            json={"auto_send_method": "email,fax"},
        )
    assert r.status_code == 422
