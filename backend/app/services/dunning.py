"""Dunning automation (v20).

Stage ladder, tied to days past ``invoice.due_date``:

    stage 1 — day +3   friendly
    stage 2 — day +7   firm
    stage 3 — day +14  final notice
    stage 4 — day +30  legal / collection escalation

The scheduler calls :func:`run_dunning_sweep` once per day at 09:00
Europe/Stockholm. The sweep picks every SENT/OVERDUE invoice that
is due for its *next* stage, records a DunningEvent row (unique on
invoice+stage), and emails the customer. The UniqueConstraint is
the durable idempotency guard — even if two workers race on the
same invoice they cannot both emit a stage.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dunning import DunningEvent
from app.models.invoicing import Customer, Invoice, InvoiceStatus
from app.models.organization import Organization
from app.services.audit import log_action
from app.services.email import send_dunning_email
from app.services.whatsapp import (
    render_whatsapp_body,
    send_sms,
    send_whatsapp,
)

log = logging.getLogger(__name__)

# Stage thresholds in days past due_date. Kept as a sorted tuple so
# the stage lookup is a plain scan.
STAGE_THRESHOLDS: list[tuple[int, int]] = [
    (1, 3),
    (2, 7),
    (3, 14),
    (4, 30),
]


# Item 18 — per-stage channel ladder. Stage 1 stays email-only (the
# friendly nudge); each subsequent stage escalates by adding a channel.
# Channels are only *attempted* when the customer has the corresponding
# contact detail and the provider env is configured; missing data simply
# skips that channel without failing the stage.
#
# Keep this as a tuple-of-strings (not a set) so the attempt order is
# stable: email first so a provider outage on WhatsApp never delays the
# email that the BFL audit trail actually requires.
STAGE_CHANNELS: dict[int, tuple[str, ...]] = {
    1: ("email",),
    2: ("email", "whatsapp"),
    3: ("email", "whatsapp", "sms"),
    4: ("email", "whatsapp", "sms"),
}


def stage_for_days_overdue(days_overdue: int, current_stage: int) -> int | None:
    """Return the next stage that should fire, or ``None`` if nothing
    new is due.

    ``current_stage`` is the invoice's existing ``dunning_stage``
    column; we only advance forward, never re-emit an earlier stage.
    """
    candidate: int | None = None
    for stage, threshold in STAGE_THRESHOLDS:
        if stage <= current_stage:
            continue
        if days_overdue >= threshold:
            candidate = stage
        else:
            break
    return candidate


async def record_dunning_event(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    invoice: Invoice,
    stage: int,
    trigger: str,
) -> bool:
    """Insert a dunning_events row and bump invoice stage.

    Returns True if a new row was inserted (caller should send email),
    False if a row already exists for this (invoice_id, stage) —
    meaning another worker beat us to it.
    """
    now_utc = datetime.now(timezone.utc)
    stmt = (
        pg_insert(DunningEvent.__table__)
        .values(
            org_id=org_id,
            invoice_id=invoice.id,
            stage=stage,
            channel="email",
            sent_at=now_utc,
            trigger=trigger,
        )
        .on_conflict_do_nothing(constraint="uq_dunning_events_invoice_stage")
        .returning(DunningEvent.__table__.c.id)
    )
    result = await db.execute(stmt)
    inserted = result.first()
    if inserted is None:
        return False

    invoice.dunning_stage = stage
    invoice.last_dunning_sent_at = now_utc
    # Surface the overdue status explicitly — the scheduler is the
    # single source of truth for OVERDUE transitions now.
    if invoice.status == InvoiceStatus.SENT:
        invoice.status = InvoiceStatus.OVERDUE
    return True


async def dispatch_dunning_channels(
    db: AsyncSession,
    *,
    invoice: Invoice,
    customer: Customer,
    org: Organization,
    stage: int,
    days_overdue: int,
    trigger: str,
) -> dict[str, bool]:
    """Send the stage's reminder through every applicable channel.

    Returns a ``{channel: success}`` dict. Per Item 18 spec:
      * Email is the mandatory baseline. A WhatsApp or SMS failure is
        logged and never blocks the email — the email carries the BFL
        audit-trail weight; the others are courtesy nudges.
      * Channels are attempted in the order defined by
        :data:`STAGE_CHANNELS`; email first so provider outages on the
        optional channels can't delay the legally-required email.
      * Each attempt writes an audit entry — ``DUNNING_REMINDER_SENT`` /
        ``_FAILED`` for email, ``DUNNING_WHATSAPP_SENT`` / ``_FAILED``
        for WhatsApp, ``DUNNING_SMS_SENT`` / ``_FAILED`` for SMS — so the
        owner can see per-channel outcomes in the audit log.
    """
    channels = STAGE_CHANNELS.get(stage, ("email",))
    results: dict[str, bool] = {}

    # Compose the short WhatsApp/SMS body once — both channels reuse it.
    short_body = render_whatsapp_body(
        stage=stage,
        customer_name=customer.company_name,
        invoice_number=invoice.invoice_number,
        amount_sek=str(invoice.total_sek),
        days_overdue=days_overdue,
        org_name=org.name,
    )

    for channel in channels:
        ok = False
        err: str | None = None

        if channel == "email":
            if not customer.email:
                err = "customer_has_no_email"
            else:
                try:
                    ok = bool(
                        await send_dunning_email(
                            to_email=customer.email,
                            customer_name=customer.company_name,
                            invoice_number=invoice.invoice_number,
                            amount_sek=str(invoice.total_sek),
                            days_overdue=days_overdue,
                            stage=stage,
                            org_name=org.name,
                        )
                    )
                    if not ok:
                        err = "resend_not_configured"
                except Exception as e:  # noqa: BLE001
                    log.warning(
                        "dunning email failed invoice=%s: %s", invoice.id, e
                    )
                    err = f"email_error: {e!r}"
            action = "DUNNING_REMINDER_SENT" if ok else "DUNNING_REMINDER_FAILED"

        elif channel == "whatsapp":
            if not customer.whatsapp_number:
                # Not an error — the customer just opted out of the channel.
                # We log a debug line but do not audit, to keep the trail
                # focused on actual delivery attempts.
                results[channel] = False
                continue
            if short_body is None:
                err = "no_template_for_stage"
            else:
                ok, err = await send_whatsapp(
                    to=customer.whatsapp_number, body=short_body
                )
            action = "DUNNING_WHATSAPP_SENT" if ok else "DUNNING_WHATSAPP_FAILED"

        elif channel == "sms":
            # Use ``whatsapp_number`` as SMS target when a dedicated
            # phone number is missing — most merchants enter the same
            # mobile in both fields anyway. Falling back this way means
            # stage 3 still hits the customer via SMS when the operator
            # has configured only the WhatsApp contact.
            target = customer.phone or customer.whatsapp_number
            if not target:
                results[channel] = False
                continue
            if short_body is None:
                err = "no_template_for_stage"
            else:
                ok, err = await send_sms(to=target, body=short_body)
            action = "DUNNING_SMS_SENT" if ok else "DUNNING_SMS_FAILED"

        else:  # pragma: no cover — STAGE_CHANNELS is closed set
            continue

        results[channel] = ok
        await log_action(
            db,
            action=action,
            org_id=invoice.org_id,
            actor_user_id=None,
            target_type="invoice",
            target_id=str(invoice.id),
            extra={
                "invoice_number": invoice.invoice_number,
                "stage": stage,
                "trigger": trigger,
                "channel": channel,
                "error": err,
            },
        )

    return results


async def run_dunning_sweep(db: AsyncSession, *, today: date | None = None) -> dict:
    """Scan all orgs for overdue invoices and emit the next stage.

    Returns a small stats dict ``{scanned, sent, skipped}`` the
    scheduler can log. Exceptions from any single invoice are
    swallowed so one bad customer row doesn't halt the sweep.

    Item 18: every applicable channel is dispatched (see
    :func:`dispatch_dunning_channels`). An invoice counts as "sent"
    when at least one channel succeeded — the critical email being
    the usual carrier. Failures on optional channels do not decrement
    the counter or roll back the stage advance.
    """
    today = today or datetime.now(timezone.utc).date()

    # Pull only invoices in SENT/OVERDUE state whose due_date has
    # already passed. Eager-load customer + org so we can compose the
    # email body without N+1 roundtrips.
    q = (
        select(Invoice, Customer, Organization)
        .join(Customer, Customer.id == Invoice.customer_id)
        .join(Organization, Organization.id == Invoice.org_id)
        .where(
            Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE]),
            Invoice.due_date < today,
            Invoice.dunning_stage < 4,
        )
    )
    rows = (await db.execute(q)).all()

    scanned = sent = skipped = 0
    for invoice, customer, org in rows:
        scanned += 1
        days_overdue = (today - invoice.due_date).days
        stage = stage_for_days_overdue(days_overdue, invoice.dunning_stage)
        if stage is None:
            skipped += 1
            continue
        if not customer.email:
            # Nothing to send to — skip quietly. Record stage-advance
            # anyway so we don't keep retrying the same invoice every
            # day for the rest of time.
            skipped += 1
            continue

        try:
            inserted = await record_dunning_event(
                db, org_id=invoice.org_id, invoice=invoice,
                stage=stage, trigger="scheduler",
            )
        except IntegrityError:
            await db.rollback()
            skipped += 1
            continue

        if not inserted:
            skipped += 1
            continue

        try:
            results = await dispatch_dunning_channels(
                db,
                invoice=invoice,
                customer=customer,
                org=org,
                stage=stage,
                days_overdue=days_overdue,
                trigger="scheduler",
            )
            if any(results.values()):
                sent += 1
            else:
                # Every channel failed — still keep the stage advance
                # so we don't retry the same dead invoice daily, but
                # surface the failure in the counter.
                log.warning(
                    "dunning all channels failed invoice=%s stage=%s results=%s",
                    invoice.id, stage, results,
                )
        except Exception as e:  # noqa: BLE001 — one bad row must not abort sweep
            log.warning(
                "dunning send failed invoice=%s stage=%s: %s",
                invoice.id, stage, e,
            )

    await db.commit()
    return {"scanned": scanned, "sent": sent, "skipped": skipped}
