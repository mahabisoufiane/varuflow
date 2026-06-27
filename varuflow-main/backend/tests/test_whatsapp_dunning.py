"""Tests for Item 18 — WhatsApp dunning.

Covers:
* Phone-number normalisation (E.164).
* Per-stage channel ladder: stage 1 email-only, stage 2 adds WhatsApp
  (iff `whatsapp_number` present), stage 3 adds SMS.
* Fallback to email-only when the WhatsApp transport fails.
* Stage advance + audit entries still happen when a channel errors.
* Customer PUT accepts and persists ``whatsapp_number``.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.features.compliance.audit_models import AuditLogEntry
from app.features.invoicing.dunning import DunningEvent
from app.features.invoicing.models import Customer, Invoice, InvoiceStatus
from app.services.dunning import (
    STAGE_CHANNELS,
    dispatch_dunning_channels,
    run_dunning_sweep,
)
from app.services.whatsapp import normalise_e164, render_whatsapp_body


# Note: `asyncio_mode = "auto"` in pyproject.toml automatically marks every
# `async def test_*` — no module-level `pytestmark` needed, and applying one
# to a module with sync tests trips a PytestWarning under pytest-asyncio 1.x.


# ─────────────────────────────────────────────────────────────────────────────
# Pure unit — no DB
# ─────────────────────────────────────────────────────────────────────────────


def test_normalise_e164_accepts_plus_prefix():
    assert normalise_e164("+46701234567") == "+46701234567"


def test_normalise_e164_accepts_double_zero_prefix():
    assert normalise_e164("0046701234567") == "+46701234567"


def test_normalise_e164_applies_default_country_to_local():
    # Swedish merchants commonly paste "070-123 45 67"; the leading zero
    # is the trunk prefix that must be stripped before adding the CC.
    assert normalise_e164("070-123 45 67") == "+46701234567"


def test_normalise_e164_strips_whitespace_and_separators():
    assert normalise_e164("+46 70 123 45 67") == "+46701234567"


def test_normalise_e164_rejects_too_short_and_too_long():
    # 7 digits total → under the 8-digit floor.
    assert normalise_e164("1234567") is None
    # 16 digits → over the 15-digit E.164 ceiling.
    assert normalise_e164("+1234567890123456") is None


def test_normalise_e164_rejects_empty_and_junk():
    assert normalise_e164("") is None
    assert normalise_e164(None) is None
    assert normalise_e164("not-a-number") is None


def test_stage_channels_ladder_matches_spec():
    """Stage 1 email; stage 2 adds WhatsApp; stage 3+ adds SMS."""
    assert STAGE_CHANNELS[1] == ("email",)
    assert "whatsapp" in STAGE_CHANNELS[2]
    assert "email" in STAGE_CHANNELS[2]
    assert "sms" in STAGE_CHANNELS[3]
    assert STAGE_CHANNELS[3] == ("email", "whatsapp", "sms")


def test_render_whatsapp_body_is_short_and_polite():
    body = render_whatsapp_body(
        stage=2,
        customer_name="Test AB",
        invoice_number="INV-2026-0001",
        amount_sek="1000.00",
        days_overdue=7,
        org_name="Varuflow",
    )
    assert body is not None
    # Spec: short and polite. One SMS segment is 160 chars — stage-2
    # template must fit with typical data.
    assert len(body) < 320
    # Must name the invoice and the org so the customer knows what
    # it's about without clicking a link.
    assert "INV-2026-0001" in body
    assert "Varuflow" in body


def test_render_whatsapp_body_returns_none_for_unknown_stage():
    assert render_whatsapp_body(
        stage=99,
        customer_name="x", invoice_number="y",
        amount_sek="1", days_overdue=1, org_name="z",
    ) is None


# ─────────────────────────────────────────────────────────────────────────────
# DB-backed tests
# ─────────────────────────────────────────────────────────────────────────────


async def _seed(
    db, org_id, *,
    days_past_due: int,
    stage: int = 0,
    total: Decimal = Decimal("1000.00"),
    email: str | None = "ar@customer.example",
    whatsapp_number: str | None = None,
    phone: str | None = None,
) -> tuple[Customer, Invoice]:
    cust = Customer(
        org_id=org_id,
        company_name="Kundbolag AB",
        email=email,
        phone=phone,
        whatsapp_number=whatsapp_number,
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


async def test_stage1_sends_email_only(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    await _seed(db_session, org.id, days_past_due=4, whatsapp_number="+46701234567")

    with patch(
        "app.services.dunning.send_dunning_email",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.dunning.send_whatsapp",
        new=AsyncMock(return_value=(True, None)),
    ) as wa_mock, patch(
        "app.services.dunning.send_sms",
        new=AsyncMock(return_value=(True, None)),
    ) as sms_mock:
        stats = await run_dunning_sweep(db_session)

    assert stats["sent"] == 1
    # Stage 1 must not touch WhatsApp or SMS even if the number exists.
    wa_mock.assert_not_awaited()
    sms_mock.assert_not_awaited()


async def test_stage2_adds_whatsapp_when_number_present(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    await _seed(
        db_session, org.id,
        days_past_due=8, stage=1,
        whatsapp_number="+46701234567",
    )

    with patch(
        "app.services.dunning.send_dunning_email",
        new=AsyncMock(return_value=True),
    ) as email_mock, patch(
        "app.services.dunning.send_whatsapp",
        new=AsyncMock(return_value=(True, None)),
    ) as wa_mock:
        await run_dunning_sweep(db_session)

    email_mock.assert_awaited_once()
    wa_mock.assert_awaited_once()
    # The audited body should have landed at the WhatsApp service.
    _, kwargs = wa_mock.await_args
    assert kwargs["to"] == "+46701234567"
    assert "INV-" in kwargs["body"]


async def test_stage2_skips_whatsapp_when_number_missing(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    await _seed(db_session, org.id, days_past_due=8, stage=1, whatsapp_number=None)

    with patch(
        "app.services.dunning.send_dunning_email",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.dunning.send_whatsapp",
        new=AsyncMock(return_value=(True, None)),
    ) as wa_mock:
        stats = await run_dunning_sweep(db_session)

    # Email still went out; invoice still counts as "sent".
    assert stats["sent"] == 1
    wa_mock.assert_not_awaited()


async def test_stage3_adds_sms(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    await _seed(
        db_session, org.id,
        days_past_due=15, stage=2,
        whatsapp_number="+46701234567",
        phone="+46701234567",
    )

    with patch(
        "app.services.dunning.send_dunning_email",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.dunning.send_whatsapp",
        new=AsyncMock(return_value=(True, None)),
    ) as wa_mock, patch(
        "app.services.dunning.send_sms",
        new=AsyncMock(return_value=(True, None)),
    ) as sms_mock:
        await run_dunning_sweep(db_session)

    wa_mock.assert_awaited_once()
    sms_mock.assert_awaited_once()


async def test_whatsapp_failure_fallbacks_to_email_only(db_session, two_orgs):
    """When WhatsApp fails, the email still lands, the invoice still
    advances, and the failure is recorded — matching the spec's
    'Fallback to email-only if WhatsApp send fails' requirement."""
    org = two_orgs["a"]["org"]
    _, inv = await _seed(
        db_session, org.id,
        days_past_due=8, stage=1,
        whatsapp_number="+46701234567",
    )

    with patch(
        "app.services.dunning.send_dunning_email",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.dunning.send_whatsapp",
        new=AsyncMock(return_value=(False, "http_500")),
    ):
        stats = await run_dunning_sweep(db_session)

    assert stats["sent"] == 1  # email succeeded → row counts as sent
    await db_session.refresh(inv)
    assert inv.dunning_stage == 2  # stage advanced despite WA failure

    actions = (
        await db_session.execute(
            select(AuditLogEntry.action).where(
                AuditLogEntry.target_id == str(inv.id)
            )
        )
    ).scalars().all()
    assert "DUNNING_REMINDER_SENT" in actions
    assert "DUNNING_WHATSAPP_FAILED" in actions


async def test_dispatch_emits_per_channel_audit_entries(db_session, two_orgs):
    org = two_orgs["a"]["org"]
    cust, inv = await _seed(
        db_session, org.id,
        days_past_due=8, stage=1,
        whatsapp_number="+46701234567",
    )

    with patch(
        "app.services.dunning.send_dunning_email",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.dunning.send_whatsapp",
        new=AsyncMock(return_value=(True, None)),
    ):
        results = await dispatch_dunning_channels(
            db_session,
            invoice=inv,
            customer=cust,
            org=org,
            stage=2,
            days_overdue=8,
            trigger="manual",
        )
    await db_session.commit()

    assert results["email"] is True
    assert results["whatsapp"] is True

    actions = (
        await db_session.execute(
            select(AuditLogEntry.action).where(
                AuditLogEntry.target_id == str(inv.id)
            )
        )
    ).scalars().all()
    assert "DUNNING_REMINDER_SENT" in actions
    assert "DUNNING_WHATSAPP_SENT" in actions


async def test_customer_put_persists_whatsapp_number(
    db_session, two_orgs, client_factory
):
    org = two_orgs["a"]["org"]
    cust = Customer(org_id=org.id, company_name="X AB")
    db_session.add(cust)
    await db_session.commit()

    async with client_factory(two_orgs["a"]["member"]) as client:
        r = await client.put(
            f"/api/invoicing/customers/{cust.id}",
            json={"whatsapp_number": "+46701234567"},
        )
    assert r.status_code == 200, r.text
    assert r.json()["whatsapp_number"] == "+46701234567"

    await db_session.refresh(cust)
    assert cust.whatsapp_number == "+46701234567"


async def test_dunning_events_idempotent_across_channels(db_session, two_orgs):
    """A second sweep on the same day for the same invoice/stage must
    not re-send any channel — the unique constraint on
    ``(invoice_id, stage)`` remains the durable guard."""
    org = two_orgs["a"]["org"]
    _, inv = await _seed(
        db_session, org.id,
        days_past_due=8, stage=1,
        whatsapp_number="+46701234567",
    )

    with patch(
        "app.services.dunning.send_dunning_email",
        new=AsyncMock(return_value=True),
    ) as email_mock, patch(
        "app.services.dunning.send_whatsapp",
        new=AsyncMock(return_value=(True, None)),
    ) as wa_mock:
        await run_dunning_sweep(db_session)
        await run_dunning_sweep(db_session)

    # Each channel fired exactly once in total across both sweeps.
    assert email_mock.await_count == 1
    assert wa_mock.await_count == 1

    rows = (
        await db_session.execute(
            select(DunningEvent).where(DunningEvent.invoice_id == inv.id)
        )
    ).scalars().all()
    assert len(rows) == 1
