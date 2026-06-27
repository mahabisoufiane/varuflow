"""Booking reminders — scheduling + delivery.

Two surfaces:

* ``schedule_reminders_for_appointment(db, appointment, customer)`` —
  called at booking time to insert the 24h and 2h ``AppointmentReminder``
  rows. Chooses the channel per customer preference (WhatsApp if a
  whatsapp_number is set, else SMS if a phone is set, else email).

* ``dispatch_due_reminders(db, now=None)`` — called by the scheduler
  every 5 minutes. Picks up pending reminders whose ``scheduled_at <=
  now`` and whose parent appointment is still ``booked`` or
  ``confirmed``, dispatches them through the existing WhatsApp/SMS
  bridge in ``app.services.whatsapp``, and marks the row ``sent`` /
  ``failed`` / ``skipped``.

Idempotency
-----------
A reminder row goes through exactly one state transition
(``pending → sent/failed/skipped``); the dispatcher filters on
``status = 'pending'`` inside the transaction, so a duplicate scheduler
tick can never double-send. The scheduler's advisory lock adds a
belt-and-braces layer on top of that for multi-replica deploys.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# Offsets before appointment start-time where we want reminders delivered.
# 24h lets the customer reschedule with enough lead time for the waitlist
# to pick up the slot; 2h is the "last-chance" nudge that reduces no-shows.
REMINDER_OFFSETS = (
    ("24h_before", timedelta(hours=24)),
    ("2h_before", timedelta(hours=2)),
)


def pick_channel_for_customer(customer) -> str:
    """Prefer WhatsApp → SMS → email based on what the customer has."""
    if customer is None:
        return "email"
    if getattr(customer, "whatsapp_number", None):
        return "whatsapp"
    if getattr(customer, "phone", None):
        return "sms"
    return "email"


def compute_reminder_schedule(
    *, start_time: datetime, channel: str, now: datetime | None = None
) -> list[dict]:
    """Pure: return the ``{type, scheduled_at}`` rows we'd emit.

    Extracted from the DB-bound ``schedule_reminders_for_appointment``
    so the math is unit-testable without the ORM import chain — the
    model module uses PEP-604 type unions that don't evaluate on
    Python 3.9 sandboxes (production runs on 3.11). Any past-due
    offsets are filtered out; same semantics as the writer below.
    """
    now = now or datetime.now(tz=timezone.utc)
    out: list[dict] = []
    for _label, offset in REMINDER_OFFSETS:
        scheduled_at = start_time - offset
        if scheduled_at <= now:
            continue
        out.append({"type": channel, "scheduled_at": scheduled_at})
    return out


async def schedule_reminders_for_appointment(
    db: AsyncSession,
    appointment,
    customer=None,
    *,
    now: datetime | None = None,
):
    """Insert ``AppointmentReminder`` rows for the two fixed offsets.

    Reminders whose computed ``scheduled_at`` is already in the past
    (e.g. a same-day booking made <2h before the appointment) are
    skipped at creation time rather than stored as ``pending`` — that
    keeps the dispatcher query small and the ``sent_at`` timeline clean.
    """
    # Lazy import — keeps this module importable on Py 3.9 sandboxes
    # (the ORM model uses ``str | None`` annotations that require 3.10+).
    from app.models.bookings import AppointmentReminder

    channel = pick_channel_for_customer(customer)
    plan = compute_reminder_schedule(
        start_time=appointment.start_time, channel=channel, now=now
    )
    created = []
    for entry in plan:
        row = AppointmentReminder(
            id=uuid.uuid4(),
            appointment_id=appointment.id,
            type=entry["type"],
            scheduled_at=entry["scheduled_at"],
            status="pending",
        )
        db.add(row)
        created.append(row)
    if created:
        await db.flush()
    return created


async def dispatch_due_reminders(
    db: AsyncSession, *, now: datetime | None = None, limit: int = 200
) -> dict:
    """Dispatch every pending reminder whose time has arrived.

    Returns a summary dict for the scheduler log: ``{"sent": n,
    "failed": n, "skipped": n}``. The dispatcher silently no-ops when
    the WhatsApp / SMS env is not configured — the send helpers return
    ``(False, "no-config")`` and we mark the row ``skipped`` so a future
    sweep doesn't retry forever.
    """
    now = now or datetime.now(tz=timezone.utc)
    # Lazy imports: see schedule_reminders_for_appointment for the Py 3.9
    # rationale. The ORM chain only needs to resolve on the scheduler's
    # execution path, not at test-collection time.
    from app.models.bookings import Appointment, AppointmentReminder

    rows = (
        await db.execute(
            select(AppointmentReminder, Appointment)
            .join(Appointment, Appointment.id == AppointmentReminder.appointment_id)
            .where(
                AppointmentReminder.status == "pending",
                AppointmentReminder.scheduled_at <= now,
            )
            .order_by(AppointmentReminder.scheduled_at.asc())
            .limit(limit)
        )
    ).all()

    from app.services.whatsapp import send_sms, send_whatsapp

    summary = {"sent": 0, "failed": 0, "skipped": 0}

    for reminder, appt in rows:
        # Don't deliver reminders for appointments that were cancelled
        # or marked no-show between booking and the reminder window.
        if appt.status not in ("booked", "confirmed"):
            reminder.status = "skipped"
            reminder.sent_at = now
            summary["skipped"] += 1
            continue

        target = await _lookup_contact(db, appt, reminder.type)
        if not target:
            reminder.status = "skipped"
            reminder.sent_at = now
            reminder.error_message = "no destination on customer record"
            summary["skipped"] += 1
            continue

        body = _render_body(appt, reminder.type)
        try:
            if reminder.type == "whatsapp":
                ok, err = await send_whatsapp(to=target, body=body)
            elif reminder.type == "sms":
                ok, err = await send_sms(to=target, body=body)
            else:
                # email fallback is not implemented here; mark skipped so
                # ops see the gap in dashboards instead of silently dropping.
                ok, err = False, "email reminders not yet implemented"
        except Exception as exc:  # defensive
            ok, err = False, str(exc)

        reminder.sent_at = now
        if ok:
            reminder.status = "sent"
            summary["sent"] += 1
        elif err == "no-config":
            reminder.status = "skipped"
            reminder.error_message = err
            summary["skipped"] += 1
        else:
            reminder.status = "failed"
            reminder.error_message = err or "send returned False"
            summary["failed"] += 1

    if rows:
        await db.commit()
    return summary


async def _lookup_contact(db: AsyncSession, appt, channel: str) -> str | None:
    """Return the phone/whatsapp number or email we should contact on."""
    if appt.customer_id is None:
        return None
    from app.models.invoicing import Customer  # lazy: avoid cycle at import

    customer = await db.get(Customer, appt.customer_id)
    if customer is None:
        return None
    if channel == "whatsapp":
        return getattr(customer, "whatsapp_number", None)
    if channel == "sms":
        return getattr(customer, "phone", None)
    return getattr(customer, "email", None)


def _render_body(appt, channel: str) -> str:
    """Minimal localisation-free template for the reminder body.

    A future item can wire in next-intl-style templates per org locale
    (en/sv/ar). For now we keep the server-side text short, brand-free,
    and free of PII so logs stay clean.
    """
    when = appt.start_time.strftime("%Y-%m-%d %H:%M")
    return f"Reminder: your appointment is on {when}. Reply STOP to unsubscribe."
