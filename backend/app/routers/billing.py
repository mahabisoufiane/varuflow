"""Stripe billing: subscription checkout, webhook, customer portal."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.organization import Organization

router = APIRouter(prefix="/api/billing", tags=["billing"])


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

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": settings.STRIPE_PRO_PRICE_ID, "quantity": 1}],
        customer_email=current_user.get("email"),
        metadata={"org_id": str(org_id)},
        success_url=f"{settings.PORTAL_BASE_URL}/settings?upgraded=1",
        cancel_url=f"{settings.PORTAL_BASE_URL}/settings",
    )
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

    session = stripe.billing_portal.Session.create(
        customer=org.stripe_customer_id,
        return_url=f"{settings.PORTAL_BASE_URL}/settings",
    )
    return PortalResponse(url=session.url)


# ── Webhook ───────────────────────────────────────────────────────────────────

@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Stripe webhook events to update org plan."""
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    stripe = _stripe()
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        org_id = session.get("metadata", {}).get("org_id")
        customer_id = session.get("customer")
        if org_id:
            org = await db.get(Organization, uuid.UUID(org_id))
            if org:
                org.plan = "PRO"
                org.stripe_customer_id = customer_id
                await db.commit()

    elif event["type"] in ("customer.subscription.deleted", "customer.subscription.paused"):
        customer_id = event["data"]["object"].get("customer")
        if customer_id:
            result = await db.execute(
                select(Organization).where(Organization.stripe_customer_id == customer_id)
            )
            org = result.scalar_one_or_none()
            if org:
                org.plan = "FREE"
                await db.commit()

    return {"received": True}
