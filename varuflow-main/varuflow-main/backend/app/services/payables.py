"""Accounts-payable automation (Item 20).

Today the only public entry point is
``create_payable_from_po(db, po, *, actor_user_id, request=None)``,
called from the PO receive endpoint when both:

* the supplier has ``create_invoice_on_receipt = True``, **and**
* no ``PayableInvoice`` already exists for this PO (idempotency).

The payable is written as ``DRAFT`` — the merchant reviews, edits, and
approves it manually. We deliberately do **not** auto-send anything;
this module never talks to email, Peppol, or any third party. The
audit log entry is the only side effect beyond the database row.

Totals derive from the PO's own line items + product tax rates; the
supplier's real bill may differ (rounding, freight, discounts) and the
merchant edits the draft before approving.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Product, PurchaseOrder
from app.models.payable_invoice import PayableInvoice
from app.services.audit import log_action

if TYPE_CHECKING:
    from fastapi import Request

log = logging.getLogger(__name__)

# Default payment terms for auto-drafted payables. Merchants edit the
# due date before approving when their supplier's terms differ. 30
# days is the Swedish wholesale default.
DEFAULT_PAYMENT_TERMS_DAYS = 30


@dataclass
class PayableCreateResult:
    """Outcome of an auto-create attempt — surfaced to the router so it
    can include a flag in the PO receive response."""

    payable: PayableInvoice | None
    created: bool  # False on idempotent short-circuit
    skipped_reason: str | None = None  # "supplier_disabled", "race_condition"


async def _compute_totals(
    db: AsyncSession, po: PurchaseOrder,
) -> tuple[Decimal, Decimal, Decimal]:
    """Return ``(subtotal, tax_amount, total)`` from the PO's lines.

    Uses each product's own ``tax_rate`` rather than a flat 25 % so
    mixed-VAT POs (food at 12 %, books at 6 %) come out right. Falls
    back to 25 % when a product was deleted between order and receive
    (FK is RESTRICT so this should be impossible, but defence in depth).
    """
    subtotal = Decimal("0.00")
    tax_amount = Decimal("0.00")
    if not po.items:
        return subtotal, tax_amount, subtotal

    product_ids = list({item.product_id for item in po.items})
    rate_rows = (
        await db.execute(
            select(Product.id, Product.tax_rate).where(Product.id.in_(product_ids))
        )
    ).all()
    rate_by_id = {pid: rate for pid, rate in rate_rows}

    for item in po.items:
        line_net = Decimal(item.line_total)
        subtotal += line_net
        rate = rate_by_id.get(item.product_id, Decimal("25.00"))
        tax_amount += (line_net * Decimal(rate) / Decimal("100")).quantize(
            Decimal("0.01")
        )

    total = (subtotal + tax_amount).quantize(Decimal("0.01"))
    return subtotal.quantize(Decimal("0.01")), tax_amount, total


async def create_payable_from_po(
    db: AsyncSession,
    po: PurchaseOrder,
    *,
    actor_user_id: uuid.UUID,
    request: "Request | None" = None,
) -> PayableCreateResult:
    """Create a DRAFT payable invoice for ``po``.

    Caller is responsible for:
      * confirming the supplier has ``create_invoice_on_receipt = True``
        (we re-check here as a defence in depth),
      * having ``po.items`` and ``po.supplier`` already loaded
        (selectinload at the call site avoids an N+1).

    Returns ``PayableCreateResult(created=False, ...)`` on idempotent
    short-circuit; never raises on a benign duplicate. Lets unrelated
    DB errors propagate so the calling transaction rolls back.
    """
    # Re-check the supplier flag — the auto-reorder scheduler also
    # transitions POs through SENT → RECEIVED in v38 and a config flip
    # mid-flight should be respected.
    if po.supplier is None or not po.supplier.create_invoice_on_receipt:
        return PayableCreateResult(
            payable=None, created=False, skipped_reason="supplier_disabled"
        )

    # Idempotency check before insert. The unique index on
    # ``payable_invoices.purchase_order_id`` is the durable guard; this
    # SELECT just lets us return the existing row to the caller without
    # a constraint-violation round-trip on the happy path.
    existing = await db.scalar(
        select(PayableInvoice).where(PayableInvoice.purchase_order_id == po.id)
    )
    if existing is not None:
        return PayableCreateResult(payable=existing, created=False)

    subtotal, tax_amount, total = await _compute_totals(db, po)
    today = date.today()
    payable = PayableInvoice(
        org_id=po.org_id,
        supplier_id=po.supplier_id,
        purchase_order_id=po.id,
        status="DRAFT",
        issue_date=today,
        due_date=today + timedelta(days=DEFAULT_PAYMENT_TERMS_DAYS),
        subtotal=subtotal,
        tax_amount=tax_amount,
        total=total,
        currency="SEK",
        notes=f"Auto-created on PO receipt (PO {str(po.id)[:8].upper()}).",
    )
    db.add(payable)
    try:
        await db.flush()
    except IntegrityError:
        # Race: a concurrent receive inserted a payable for this PO
        # between our SELECT and our INSERT. The unique index caught it.
        # Roll back the flush state and return the winner.
        await db.rollback()
        existing = await db.scalar(
            select(PayableInvoice).where(PayableInvoice.purchase_order_id == po.id)
        )
        return PayableCreateResult(
            payable=existing, created=False, skipped_reason="race_condition"
        )

    await log_action(
        db,
        action="PAYABLE_INVOICE_AUTO_CREATED",
        org_id=po.org_id,
        actor_user_id=actor_user_id,
        target_type="payable_invoice",
        target_id=str(payable.id),
        request=request,
        extra={
            "purchase_order_id": str(po.id),
            "supplier_id": str(po.supplier_id),
            "total": str(total),
            "currency": "SEK",
        },
    )
    return PayableCreateResult(payable=payable, created=True)
