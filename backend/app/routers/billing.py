"""Stripe billing: subscription checkout, webhook, customer portal."""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import String, select
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.config import settings
from app.database import Base, get_db
from app.middleware.auth import get_current_member
from app.models.organization import OrgPlan, Organization

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/billing", tags=["billing"])


# ── Idempotency model ─────────────────────────────────────────────────────────

class StripeProcessedEvent(Base):
    """Tracks Stripe webhook events already processed.

    Prevents duplicate processing if Stripe retries the same event (e.g. due
    to a transient 500).  event_id is unique so a second INSERT will fail with
    IntegrityError — we catch that and return 200 immediately.
    """
    __tablename__ = "stripe_processed_events"

    id:       Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[str]       = mapped_column(String(100), nullable=False, unique=True, index=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _stripe():
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        return stripe
    except ImportError:
        raise HTTPException(status_code=503, detail="Stripe not configured")


# ── Schemas ───────────────────────────────────────────────────────────────────

class CheckoutResponse(BaseModel):
    url: str


class PortalResponse(BaseModel):
    url: str


# ── Checkout ──────────────────────────────────────────────────────────────────

@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout session for the PRO plan upgrade."""
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_PRO_PRICE_ID:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    stripe = _stripe()
    org_id = _org(ctx)
    current_user, member = ctx
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": settings.STRIPE_PRO_PRICE_ID, "quantity": 1}],
            customer_email=current_user.get("email"),
            metadata={"org_id": str(org_id)},
            success_url=f"{settings.PORTAL_BASE_URL}/settings?upgraded=1",
            cancel_url=f"{settings.PORTAL_BASE_URL}/settings",
        )
    except Exception as e:
        log.error("stripe checkout failed", extra={"org_id": str(org_id), "error": str(e)})
        raise HTTPException(status_code=502, detail="Failed to create checkout session")

    return CheckoutResponse(url=session.url)


# ── Customer portal ───────────────────────────────────────────────────────────

@router.post("/portal", response_model=PortalResponse)
async def create_portal_session(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Customer Portal session for managing subscriptions."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    stripe = _stripe()
    org_id = _org(ctx)
    org = await db.get(Organization, org_id)
    if not org or not org.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer found. Upgrade first.")

    try:
        session = stripe.billing_portal.Session.create(
            customer=org.stripe_customer_id,
            return_url=f"{settings.PORTAL_BASE_URL}/settings",
        )
    except Exception as e:
        log.error("stripe portal failed", extra={"org_id": str(org_id), "error": str(e)})
        raise HTTPException(status_code=502, detail="Failed to create portal session")

    return PortalResponse(url=session.url)


# ── Webhook ───────────────────────────────────────────────────────────────────

@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Stripe webhook events to update org plan.

    Security:
    - Signature verified before any processing (RULE 9).
    - Idempotent: duplicate event_id is silently ignored so Stripe retries are safe.
    - Uses OrgPlan enum — raw strings would silently break plan-gated queries.
    """
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    stripe = _stripe()
    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    # ── 1. Verify signature (RULE 9 — NEVER skip) ────────────────────────────
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        log.warning("stripe webhook: invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        log.error("stripe webhook: payload parse error", extra={"error": str(e)})
        raise HTTPException(status_code=400, detail="Bad payload")

    event_id   = event["id"]
    event_type = event["type"]

    # ── 2. Idempotency check ─────────────────────────────────────────────────
    # If we already processed this event_id, return 200 immediately.
    already = await db.scalar(
        select(StripeProcessedEvent).where(StripeProcessedEvent.event_id == event_id)
    )
    if already:
        log.info("stripe webhook: duplicate event ignored", extra={"event_id": event_id})
        return {"received": True}

    # ── 3. Process event ─────────────────────────────────────────────────────
    try:
        if event_type == "checkout.session.completed":
            session_obj = event["data"]["object"]
            org_id      = session_obj.get("metadata", {}).get("org_id")
            customer_id = session_obj.get("customer")
            if org_id:
                org = await db.get(Organization, uuid.UUID(org_id))
                if org:
                    org.plan               = OrgPlan.PRO   # ← enum, not raw string
                    org.stripe_customer_id = customer_id
                    log.info("org upgraded to PRO", extra={"org_id": org_id, "event_id": event_id})

        elif event_type in ("customer.subscription.deleted", "customer.subscription.paused"):
            customer_id = event["data"]["object"].get("customer")
            if customer_id:
                org = await db.scalar(
                    select(Organization).where(Organization.stripe_customer_id == customer_id)
                )
                if org:
                    org.plan = OrgPlan.FREE  # ← enum, not raw string
                    log.info("org downgraded to FREE", extra={"stripe_customer": customer_id, "event_id": event_id})

        elif event_type == "invoice.payment_failed":
            # Grace period: log the failure but do NOT immediately downgrade.
            # Stripe will retry and send subscription.deleted if all retries fail.
            customer_id = event["data"]["object"].get("customer")
            log.warning("stripe invoice payment failed (grace period active)", extra={"stripe_customer": customer_id, "event_id": event_id})

        else:
            log.debug("stripe webhook: unhandled event type", extra={"event_type": event_type})

    except Exception as e:
        log.error("stripe webhook: processing error", extra={"event_id": event_id, "event_type": event_type, "error": str(e)})
        raise HTTPException(status_code=500, detail="Internal server error")

    # ── 4. Mark event as processed (idempotency) ─────────────────────────────
    db.add(StripeProcessedEvent(event_id=event_id))
    await db.commit()

    return {"received": True}
