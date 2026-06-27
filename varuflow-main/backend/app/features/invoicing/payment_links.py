"""Invoicing routes: Stripe payment links + invoice payment webhook."""
import logging
import uuid
from datetime import date
from decimal import Decimal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from .models import (
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentMethod,
)

from ._shared import (
    _check_invoice_email_cooldown,
    _org,
)

log = logging.getLogger(__name__)
router = APIRouter()


# ── Stripe payment link ────────────────────────────────────────────────────────

class PaymentLinkOut(BaseModel):
    url: str
    status: str


@router.post("/invoices/{invoice_id}/payment-link", response_model=PaymentLinkOut)
async def create_payment_link(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout session and email the payment link to the customer."""
    from app.config import settings
    from app.services.email import send_payment_link_email

    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe not configured — add STRIPE_SECRET_KEY")

    org_id = _org(ctx)
    try:
        # Lock the invoice row so two concurrent /payment-link calls can't
        # both create a Stripe Checkout session and both overwrite the
        # stored id — the orphaned session would never get its status
        # updated via webhook against this invoice.
        result = await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
            .where(Invoice.id == invoice_id, Invoice.org_id == org_id)
            .with_for_update()
        )
        inv = result.scalar_one_or_none()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        if inv.status == InvoiceStatus.PAID:
            raise HTTPException(status_code=422, detail="Invoice is already paid")
        # Block payment links on DRAFT invoices. A DRAFT is a work-in-progress
        # document — line items, totals and due dates can still be edited by
        # the seller. Emailing a customer a Stripe checkout URL for an
        # unfinished invoice lets them pay against a figure the org hasn't
        # formally issued, and any later edit to the invoice would leave the
        # collected amount disagreeing with the bookkept total (a BFL
        # audit-trail violation). Force the seller to mark it SENT first.
        if inv.status == InvoiceStatus.DRAFT:
            raise HTTPException(
                status_code=422,
                detail="Cannot create a payment link for a DRAFT invoice — mark it Sent first",
            )
        if not inv.customer.email:
            raise HTTPException(status_code=422, detail="Customer has no email address")

        # Reuse an existing pending link if we already created one — avoids
        # generating multiple Stripe sessions for the same invoice on
        # repeated clicks and gives a consistent URL if the customer already
        # received it by email.
        #
        # Stripe Checkout sessions auto-expire 24 h after creation. Without
        # verifying the session is still "open" we would keep handing the
        # customer the same dead URL for days after the first click, and
        # they'd land on a Stripe error page with no recourse. Round-trip
        # to Stripe to confirm the session is still usable; if it expired,
        # fall through and mint a fresh one.
        if inv.stripe_payment_link_url and inv.stripe_payment_link_status == "pending":
            import stripe as _stripe_early
            _stripe_early.api_key = settings.STRIPE_SECRET_KEY
            try:
                existing = _stripe_early.checkout.Session.retrieve(inv.stripe_checkout_session_id)
                existing_status = (existing or {}).get("status")
                if existing_status == "open":
                    return PaymentLinkOut(url=inv.stripe_payment_link_url, status="pending")
                if existing_status == "complete":
                    # The customer has already completed this checkout —
                    # either the webhook has already fired (in which case
                    # inv.status == PAID would have short-circuited above)
                    # or it is in-flight and about to arrive. Either way
                    # minting a fresh Stripe session here would generate
                    # a SECOND payment URL for the same invoice and
                    # invite the customer to pay a second time. Return
                    # the existing URL with a "paid" marker so the UI
                    # can surface "awaiting confirmation" instead of a
                    # "pay now" button. Persist the marker so later
                    # clicks short-circuit without another Stripe call.
                    inv.stripe_payment_link_status = "paid"
                    await db.commit()
                    return PaymentLinkOut(url=inv.stripe_payment_link_url, status="paid")
                # Otherwise the session is "expired" (or an unknown state);
                # mark it and fall through to create a new session below.
                inv.stripe_payment_link_status = "expired"
            except Exception as e:
                # If Stripe is briefly unreachable, returning the cached URL
                # is still safer than 502'ing the user — a short window of
                # potentially-stale links is acceptable for transient errors.
                log.warning(
                    "payment_link session retrieve failed | org_id=%s | invoice=%s | err=%s",
                    org_id, invoice_id, str(e),
                )
                return PaymentLinkOut(url=inv.stripe_payment_link_url, status="pending")

        # Outbound-email throttle — stop an abusive session from triggering
        # a flood of Stripe session creations + customer emails.
        _check_invoice_email_cooldown(org_id, invoice_id, "payment_link")

        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY

        # Charge the REMAINING balance, not the full invoice total. If the
        # customer already made a partial payment via /payments (e.g. a
        # manually recorded bank transfer), the prior code would bill the
        # full gross again via Stripe, and the subsequent
        # stripe_invoice_webhook would insert a full-amount Payment row
        # on top of the existing partial. Result: total recorded payments
        # > invoice total, a Swedish bokföringslagen audit violation and
        # a confused customer double-charged. Compute remaining here and
        # reject if nothing is owed (covers the race where a last manual
        # payment closed the balance between the PAID-status check above
        # and this point — we hold the row lock but payments may have
        # been recorded inside the same transaction window by an earlier
        # call that already committed).
        existing_paid_result = await db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.invoice_id == invoice_id
            )
        )
        existing_paid = Decimal(str(existing_paid_result or 0))
        remaining = inv.total_sek - existing_paid
        if remaining <= 0:
            raise HTTPException(
                status_code=422,
                detail="Invoice is already fully paid — no payment link needed.",
            )
        amount_ore = int(remaining * 100)  # SEK → öre, remaining balance only
        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                currency="sek",
                line_items=[{
                    "price_data": {
                        "currency": "sek",
                        "unit_amount": amount_ore,
                        "product_data": {
                            "name": f"Invoice {inv.invoice_number}",
                            "description": f"Due {inv.due_date}",
                        },
                    },
                    "quantity": 1,
                }],
                customer_email=inv.customer.email,
                metadata={"invoice_id": str(inv.id), "org_id": str(org_id)},
                success_url=f"{settings.PORTAL_BASE_URL}/invoices/{inv.id}?paid=1",
                cancel_url=f"{settings.PORTAL_BASE_URL}/invoices/{inv.id}",
            )
        except stripe.error.StripeError as e:
            log.error(
                "payment_link stripe_error | org_id=%s | invoice=%s | err=%s",
                org_id, invoice_id, str(e),
            )
            raise HTTPException(status_code=502, detail="Payment provider temporarily unavailable")

        inv.stripe_checkout_session_id = session.id
        inv.stripe_payment_link_url = session.url
        inv.stripe_payment_link_status = "pending"
        await db.commit()

        # Email the payment link (best-effort — don't fail the request if
        # email delivery has a hiccup; the link is still saved).
        try:
            # Fetch the org for the "From" header. Deferred until here so
            # we don't pay for the lookup when the customer has no email.
            from app.features.auth.organization import Organization as _Organization
            _org_row = await db.get(_Organization, org_id)
            _org_name = _org_row.name if _org_row else "Varuflow"
            await send_payment_link_email(
                to_email=inv.customer.email,
                customer_name=inv.customer.company_name,
                invoice_number=inv.invoice_number,
                # Show the REMAINING balance the link actually charges —
                # not `inv.total_sek`. A partially-paid invoice would
                # otherwise tell the customer "Pay 10 000 SEK" while the
                # Stripe session only bills the outstanding 3 000 SEK,
                # confusing the customer and breaking reconciliation
                # with their own accounts-payable records.
                total_sek=f"{remaining:.2f}",
                due_date=str(inv.due_date),
                payment_url=session.url,
                org_name=_org_name,
            )
        except Exception as e:
            log.warning(
                "payment_link email failed | org_id=%s | invoice=%s | err=%s",
                org_id, invoice_id, str(e),
            )

        return PaymentLinkOut(url=session.url, status="pending")
    except HTTPException:
        raise
    except Exception as e:
        log.error("payment_link failed | org_id=%s | invoice=%s | err=%s", org_id, invoice_id, str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/invoices/{invoice_id}/payment-link", response_model=PaymentLinkOut)
async def get_payment_link(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.org_id == org_id)
    )
    inv = result.scalar_one_or_none()
    if not inv or not inv.stripe_payment_link_url:
        raise HTTPException(status_code=404, detail="No payment link found")
    return PaymentLinkOut(url=inv.stripe_payment_link_url, status=inv.stripe_payment_link_status or "pending")



# ── Stripe webhook (invoice payment) ──────────────────────────────────────────

@router.post("/webhooks/stripe", status_code=200)
async def stripe_invoice_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Stripe payment.succeeded → auto-mark invoice as PAID."""
    from app.config import settings
    from app.features.billing.billing import StripeProcessedEvent

    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook secret not configured")

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    payload = await request.body()
    # DoS guard — real Stripe events are well under 256 KB
    if len(payload) > 256 * 1024:
        raise HTTPException(status_code=413, detail="Payload too large")
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payload")

    event_id = event.get("id") or ""
    if not event_id:
        raise HTTPException(status_code=400, detail="Missing event id")

    # Idempotency: insert-first with ON CONFLICT DO NOTHING so two concurrent
    # deliveries of the same event_id cannot both pass the check and both
    # mark the invoice PAID. Only the INSERT that actually wrote the row
    # proceeds; the loser returns duplicate=True without side effects.
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    ins = (
        pg_insert(StripeProcessedEvent.__table__)
        .values(event_id=event_id)
        .on_conflict_do_nothing(index_elements=["event_id"])
    )
    result = await db.execute(ins)
    if result.rowcount == 0:
        await db.commit()
        return {"received": True, "duplicate": True}

    processing_ok = True
    try:
        if event["type"] == "checkout.session.completed":
            session_obj = event["data"]["object"]
            invoice_id_str = session_obj.get("metadata", {}).get("invoice_id")
            if invoice_id_str:
                try:
                    inv_id = uuid.UUID(invoice_id_str)
                except ValueError:
                    inv_id = None
                if inv_id:
                    # Fetch org_id from webhook metadata for defense-in-depth.
                    # Stripe signature already proves the payload is authentic,
                    # but filtering by org_id prevents cross-org mark-as-paid
                    # if the signing secret were ever rotated late.
                    org_id_str = session_obj.get("metadata", {}).get("org_id")
                    org_id_filter = []
                    if org_id_str:
                        try:
                            org_id_filter = [Invoice.org_id == uuid.UUID(org_id_str)]
                        except ValueError:
                            pass
                    # Row-lock the invoice so concurrent webhook deliveries
                    # for the same invoice (e.g. checkout.session.completed
                    # followed closely by payment_intent.succeeded) can't
                    # both double-mark or double-insert payments.
                    inv = await db.scalar(
                        select(Invoice)
                        .where(Invoice.id == inv_id, *org_id_filter)
                        .with_for_update()
                    )
                    if inv and inv.status != InvoiceStatus.PAID:
                        inv.status = InvoiceStatus.PAID
                        inv.stripe_payment_link_status = "paid"
                        # Record the payment so it appears in /payments and
                        # the aging report reflects the collected amount.
                        # Bokföringslagen requires a trackable payment row;
                        # silently flipping status leaves an accounting gap.
                        amount_ore = session_obj.get("amount_total")
                        paid_amount = (
                            Decimal(str(amount_ore)) / Decimal("100")
                            if amount_ore is not None
                            else inv.total_sek
                        )
                        db.add(
                            Payment(
                                org_id=inv.org_id,
                                invoice_id=inv.id,
                                amount=paid_amount,
                                payment_date=date.today(),
                                # Stripe payments are card transactions and
                                # `PaymentMethod` only has BANK_TRANSFER /
                                # CARD / CASH / OTHER — "stripe" is not a
                                # valid enum value. The webhook previously
                                # passed `payment_method=...` and `note=...`
                                # which aren't columns on Payment, causing
                                # a silent TypeError that the outer except
                                # swallowed — invoices never actually got
                                # marked PAID in production. Use the real
                                # column names + a valid enum + reference.
                                method=PaymentMethod.CARD,
                                reference=f"stripe:{event_id}"[:255],
                            )
                        )
                    elif inv and inv.status == InvoiceStatus.PAID:
                        # Already paid — ensure the payment_link status
                        # stays consistent but don't insert a second Payment.
                        inv.stripe_payment_link_status = "paid"
    except Exception:
        # Do NOT swallow silently-and-commit: if we persist the
        # StripeProcessedEvent marker while the invoice update failed,
        # Stripe will treat the event as delivered (we returned 200) and
        # never retry, so the invoice stays UNPAID forever even though the
        # customer was charged. Instead roll back BOTH the idempotency row
        # and any partial invoice writes, and surface a 500 so Stripe
        # retries the event within its replay window.
        import logging
        logging.getLogger(__name__).exception(
            "stripe invoice webhook: processing error | event_id=%s", event_id,
        )
        processing_ok = False

    if not processing_ok:
        await db.rollback()
        raise HTTPException(
            status_code=500, detail="Webhook processing failed; will be retried"
        )

    # Commit both the idempotency row and any invoice update together.
    try:
        await db.commit()
    except IntegrityError:
        # Defence-in-depth: another race we didn't catch above.
        await db.rollback()

    return {"received": True}


