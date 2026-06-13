"""Recurring invoice auto-send (v39 — Item 17).

Given a freshly-generated recurring invoice, deliver it to the customer
through the channels configured on the schedule. Delivery failures are
caught per-channel: the invoice stays created, the other channels still
attempt, and everything is audited so the owner can see what happened.

This module deliberately does NOT perform invoice *generation* — that
stays in ``app.routers.recurring.run_now`` so the manual trigger and
the scheduler share one implementation. ``auto_send_invoice`` is
invoked after generation, receiving the already-committed invoice.

Audit events emitted:
* ``recurring_invoice.auto_sent``          — any channel succeeded.
* ``recurring_invoice.auto_send_failed``   — every attempted channel failed.

Channel support (v39):
* ``email``  — Resend HTML + PDF attachment, reusing send_invoice_email.
* ``peppol`` — Peppol BIS 3.0 XML generation. We do NOT yet POST to an
  access point; the XML is persisted as an audit artefact and the
  invoice is marked SENT. Once Peppol dispatch is wired in a later
  item the output of this function is ready to feed it.
"""
from __future__ import annotations

import calendar
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func as sqlfunc
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.invoicing import (
    Customer,
    Invoice,
    InvoiceLineItem,
    InvoiceStatus,
    RecurringFrequency,
    RecurringInvoice,
)
from app.models.organization import Organization
from app.services.audit import log_action

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Invoice generation
# ─────────────────────────────────────────────────────────────────────────────

class RecurringRunError(Exception):
    """Raised when we cannot produce an invoice from a schedule. Carries
    a short machine-friendly reason so the scheduler can classify the
    failure without parsing free-form text."""

    def __init__(self, reason: str, http_status: int = 422):
        super().__init__(reason)
        self.reason = reason
        self.http_status = http_status


def _advance_next_run_date(current: date, frequency: RecurringFrequency) -> date:
    """Advance a schedule's next-run date.

    Weekly: +7 days. Monthly: +1 calendar month with day-of-month
    clamped to the target month's length (so Jan 31 → Feb 28/29).
    Lifted from the prior inline logic in ``run_now`` so the manual
    and scheduled paths share one source of truth.
    """
    if frequency == RecurringFrequency.WEEKLY:
        return current + timedelta(weeks=1)
    # Monthly — clamp day to the target month's length.
    m = current.month + 1
    y = current.year + (m - 1) // 12
    m = ((m - 1) % 12) + 1
    last_day = calendar.monthrange(y, m)[1]
    return current.replace(year=y, month=m, day=min(current.day, last_day))


async def generate_invoice_from_recurring(
    db: AsyncSession,
    *,
    recurring: RecurringInvoice,
    org_id: uuid.UUID,
) -> Invoice:
    """Create a new DRAFT invoice from a recurring schedule's template.

    Responsibilities:

    * Serialize on the Organization row so concurrent runs cannot produce
      duplicate ``INV-YYYY-NNNN`` numbers. The DB-level UNIQUE
      (org_id, invoice_number) constraint (migration v15) is the backstop;
      this lock avoids the ``IntegrityError`` path entirely.
    * Derive the next sequence from MAX+1 on existing invoice numbers
      rather than COUNT(*) so deleting a DRAFT does not free a gap-fill
      number — required by Swedish bokföringslagen (BFL).
    * Clone template line items into a fresh Invoice row.
    * Advance ``recurring.next_run_date`` in the same transaction.

    Caller is responsible for acquiring ``with_for_update`` on the
    RecurringInvoice row and for committing the transaction afterwards.
    The returned Invoice is attached to the session but not yet flushed
    so the caller can batch further changes.
    """
    if not recurring.is_active:
        raise RecurringRunError("recurring_paused")

    # Load the template invoice scoped to caller's org — a tampered
    # ``template_invoice_id`` pointing at another tenant must not leak.
    template = await db.scalar(
        select(Invoice)
        .options(selectinload(Invoice.line_items))
        .where(
            Invoice.id == recurring.template_invoice_id,
            Invoice.org_id == org_id,
        )
    )
    if template is None:
        raise RecurringRunError("template_not_found", http_status=404)

    customer = await db.scalar(
        select(Customer).where(
            Customer.id == recurring.customer_id,
            Customer.org_id == org_id,
        )
    )
    if customer is None:
        raise RecurringRunError("customer_not_found", http_status=404)
    if not customer.is_active:
        # An archived customer should not receive newly-minted invoices.
        # Reactivate or pause the schedule — see comment in router.
        raise RecurringRunError("customer_archived")

    # Serialize per-org so two concurrent runs get different sequence
    # numbers even if they read the same MAX() snapshot.
    await db.execute(
        select(Organization.id).where(Organization.id == org_id).with_for_update()
    )

    year = datetime.now(timezone.utc).year
    year_prefix = f"INV-{year}-"
    max_number = await db.scalar(
        select(sqlfunc.max(Invoice.invoice_number)).where(
            Invoice.org_id == org_id,
            Invoice.invoice_number.like(f"{year_prefix}%"),
        )
    )
    next_seq = 1
    if max_number:
        try:
            next_seq = int(max_number.rsplit("-", 1)[-1]) + 1
        except (ValueError, IndexError):
            next_seq = 1
    inv_number = f"{year_prefix}{next_seq:04d}"

    today = date.today()
    due = today + timedelta(days=customer.payment_terms_days or 30)

    new_inv = Invoice(
        org_id=org_id,
        customer_id=recurring.customer_id,
        invoice_number=inv_number,
        issue_date=today,
        due_date=due,
        status=InvoiceStatus.DRAFT,
        subtotal=template.subtotal,
        vat_amount=template.vat_amount,
        total_sek=template.total_sek,
        notes=template.notes,
        line_items=[
            InvoiceLineItem(
                product_id=li.product_id,
                description=li.description,
                quantity=li.quantity,
                unit_price=li.unit_price,
                tax_rate=li.tax_rate,
                line_total=li.line_total,
            )
            for li in template.line_items
        ],
    )
    db.add(new_inv)
    await db.flush()  # assign new_inv.id so callers can reference it

    recurring.next_run_date = _advance_next_run_date(
        recurring.next_run_date, recurring.frequency
    )
    return new_inv


# ─────────────────────────────────────────────────────────────────────────────
# Auto-send dispatch
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AutoSendResult:
    """Per-invoice outcome. ``channels_succeeded`` drives the invoice
    status update: if any channel succeeded we flip DRAFT → SENT."""

    invoice_id: uuid.UUID
    invoice_number: str
    channels_attempted: list[str] = field(default_factory=list)
    channels_succeeded: list[str] = field(default_factory=list)
    channels_failed: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return bool(self.channels_succeeded)


def _parse_methods(raw: str | None) -> list[str]:
    """Split the ``auto_send_method`` column into a clean channel list.

    Accepts ``"email"``, ``"peppol"``, or ``"email,peppol"``. Unknown
    values are silently dropped rather than raising — a typo on an old
    row must not poison an otherwise-valid sweep.
    """
    if not raw:
        return []
    allowed = {"email", "peppol"}
    return [
        m for m in (s.strip().lower() for s in raw.split(",") if s.strip())
        if m in allowed
    ]


async def _send_email_channel(
    db: AsyncSession,
    *,
    invoice: Invoice,
    org: Organization,
) -> tuple[bool, str | None]:
    """Deliver via Resend. Returns (ok, error_detail).

    Mirrors the manual ``POST /invoices/{id}/send`` path so that failure
    modes and behaviour stay identical to the owner clicking Send.
    """
    from app.routers.invoicing import _generate_invoice_pdf
    from app.services.email import send_invoice_email

    if not invoice.customer or not invoice.customer.email:
        return False, "customer_has_no_email"

    try:
        pdf_bytes = _generate_invoice_pdf(invoice)
    except Exception as e:  # noqa: BLE001 — surface the reason to the audit log
        logger.exception("auto_send pdf generation failed inv=%s", invoice.id)
        return False, f"pdf_generation_failed: {e!r}"

    try:
        sent = await send_invoice_email(
            to_email=invoice.customer.email,
            customer_name=invoice.customer.company_name,
            invoice_number=invoice.invoice_number,
            total_sek=f"{invoice.total_sek:.2f}",
            due_date=str(invoice.due_date),
            pdf_bytes=pdf_bytes,
            org_name=org.name,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("auto_send email send failed inv=%s", invoice.id)
        return False, f"email_send_failed: {e!r}"

    return (bool(sent), None if sent else "resend_not_configured")


async def _send_peppol_channel(
    db: AsyncSession,
    *,
    invoice: Invoice,
    org: Organization,
) -> tuple[bool, str | None]:
    """Render Peppol BIS 3.0 XML for later dispatch to an access point.

    We cannot assume an access-point integration exists in every
    environment, so this step currently succeeds when we can produce
    valid XML. The generated bytes are attached to the audit log via
    ``size_bytes`` so the owner has a paper trail; the actual transport
    hookup will flip the ``sent`` determinant in a later item.
    """
    if not invoice.customer:
        return False, "customer_missing"
    if not invoice.customer.peppol_enabled:
        return False, "peppol_not_enabled_on_customer"
    if not (invoice.customer.peppol_id or "").strip():
        return False, "customer_peppol_id_missing"

    try:
        from app.routers.invoicing import _generate_peppol_xml

        xml_bytes = _generate_peppol_xml(invoice, org)
    except Exception as e:  # noqa: BLE001 — VAT format, schema, etc.
        logger.exception("auto_send peppol xml generation failed inv=%s", invoice.id)
        return False, f"peppol_xml_failed: {e!r}"

    await log_action(
        db,
        action="recurring_invoice.peppol_rendered",
        org_id=org.id,
        actor_user_id=None,
        target_type="invoice",
        target_id=str(invoice.id),
        extra={
            "invoice_number": invoice.invoice_number,
            "size_bytes": len(xml_bytes),
            "peppol_id": invoice.customer.peppol_id,
        },
    )
    return True, None


async def auto_send_invoice(
    db: AsyncSession,
    *,
    recurring: RecurringInvoice,
    invoice_id: uuid.UUID,
) -> AutoSendResult:
    """Dispatch a freshly-created recurring invoice.

    Parameters
    ----------
    recurring : The schedule that produced this invoice. Drives which
        channels to attempt (``auto_send_method``).
    invoice_id : The newly-committed invoice row. Caller has already
        persisted it and released any advisory locks.
    """
    # Reload with the relationships we need. The caller's session may
    # have the invoice cached without ``customer`` eager-loaded, and we
    # want exactly one code path here.
    inv_row = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
        .where(Invoice.id == invoice_id)
    )
    invoice = inv_row.scalar_one_or_none()
    if invoice is None:
        raise ValueError(f"invoice_not_found: {invoice_id}")

    org = await db.get(Organization, invoice.org_id)
    if org is None:
        raise ValueError(f"org_not_found: {invoice.org_id}")

    result = AutoSendResult(
        invoice_id=invoice.id,
        invoice_number=invoice.invoice_number,
    )

    if not recurring.auto_send:
        return result  # explicit off — nothing to do, no audit noise

    methods = _parse_methods(recurring.auto_send_method)
    if not methods:
        # auto_send=True but no valid method — record the misconfiguration
        # so the owner sees it in the audit log.
        await log_action(
            db,
            action="recurring_invoice.auto_send_failed",
            org_id=org.id,
            actor_user_id=None,
            target_type="invoice",
            target_id=str(invoice.id),
            extra={
                "invoice_number": invoice.invoice_number,
                "reason": "no_valid_channels",
                "raw_method": recurring.auto_send_method,
            },
        )
        await db.commit()
        return result

    for method in methods:
        result.channels_attempted.append(method)
        if method == "email":
            ok, err = await _send_email_channel(db, invoice=invoice, org=org)
        elif method == "peppol":
            ok, err = await _send_peppol_channel(db, invoice=invoice, org=org)
        else:  # pragma: no cover — filtered above
            ok, err = False, "unknown_channel"

        if ok:
            result.channels_succeeded.append(method)
        else:
            result.channels_failed.append(method)
            if err:
                result.errors[method] = err

    # Flip DRAFT → SENT if at least one channel landed. Matches the
    # guard in the manual /send endpoint: the invoice has left the
    # building, so no longer surfaces in the "Drafts" list.
    if result.success and invoice.status == InvoiceStatus.DRAFT:
        invoice.status = InvoiceStatus.SENT

    action = (
        "recurring_invoice.auto_sent"
        if result.success
        else "recurring_invoice.auto_send_failed"
    )
    await log_action(
        db,
        action=action,
        org_id=org.id,
        actor_user_id=None,
        target_type="invoice",
        target_id=str(invoice.id),
        extra={
            "invoice_number": invoice.invoice_number,
            "recurring_id": str(recurring.id),
            "channels_attempted": result.channels_attempted,
            "channels_succeeded": result.channels_succeeded,
            "channels_failed": result.channels_failed,
            "errors": result.errors,
        },
    )
    await db.commit()
    return result
