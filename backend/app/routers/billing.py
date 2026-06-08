"""Stripe billing: subscription checkout, webhook, customer portal."""
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, String, func, select
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.config import settings
from app.database import Base, get_db
from app.middleware.auth import get_current_member
from app.models.organization import OrgPlan, OrgRole, Organization, SubscriptionPause
from app.services.audit import log_action

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
    # Populated at insert time by the DB. Used by the token_cleanup scheduler
    # to prune entries past Stripe's 30-day replay window.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


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

class CheckoutRequest(BaseModel):
    plan: str = Field(default="professional", pattern=r"^(starter|professional)$")


class CheckoutResponse(BaseModel):
    url: str


class PortalResponse(BaseModel):
    url: str


# ── Price ID resolver ─────────────────────────────────────────────────────────

def _price_id_for_plan(plan: str) -> str:
    """Return the Stripe price ID for the requested plan tier.

    Both 'starter' and 'professional' map to OrgPlan.PRO in the database —
    the distinction is purely in the Stripe subscription amount. Enterprise
    is handled via contact-sales and never reaches checkout.
    """
    if plan == "starter":
        price_id = settings.STRIPE_STARTER_PRICE_ID or settings.STRIPE_PRO_PRICE_ID
    else:
        price_id = settings.STRIPE_PRO_PRICE_ID
    if not price_id:
        raise HTTPException(status_code=503, detail="Stripe price not configured for this plan")
    return price_id


# ── Checkout ──────────────────────────────────────────────────────────────────

@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    body: CheckoutRequest = CheckoutRequest(),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout session for a paid plan upgrade.

    Accepts an optional ``plan`` body field ("starter" or "professional").
    Both resolve to OrgPlan.PRO in the database; the difference is the
    Stripe price charged.

    Owner-only: starting a subscription or changing the payment method must
    be the data-controller's decision. A non-owner could otherwise upgrade
    the org (billed to whoever completes checkout) or create a duplicate
    subscription in parallel with the existing one.
    """
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    stripe = _stripe()
    org_id = _org(ctx)
    current_user, member = ctx
    if member.role != OrgRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the organization owner can manage billing")
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    # Block a second checkout while a subscription is already live.
    if org.plan == OrgPlan.PRO and org.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization is already on a paid plan. Use the customer portal to manage the subscription.",
        )

    price_id = _price_id_for_plan(body.plan)

    try:
        # Re-use the existing Stripe customer when the org has one (e.g. a
        # previous subscription was cancelled and the owner is now re-
        # subscribing). Passing `customer_email` instead would make Stripe
        # mint a *new* customer record every time, fragmenting billing
        # history, orphaning the old card/tax/address on file, and leaving
        # duplicate PII rows on Stripe that webhooks can no longer match
        # back to this org. Only fall back to `customer_email` on the very
        # first checkout (no stripe_customer_id on record).
        checkout_kwargs: dict = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "metadata": {"org_id": str(org_id), "plan": body.plan},
            "success_url": f"{settings.PORTAL_BASE_URL}/settings?upgraded=1",
            "cancel_url": f"{settings.PORTAL_BASE_URL}/settings",
        }
        if org.stripe_customer_id:
            checkout_kwargs["customer"] = org.stripe_customer_id
        else:
            email = current_user.get("email")
            if email:
                checkout_kwargs["customer_email"] = email
        session = stripe.checkout.Session.create(**checkout_kwargs)
    except HTTPException:
        raise
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
    """Create a Stripe Customer Portal session for managing subscriptions.

    Owner-only: the portal exposes cancellation, payment-method changes
    and invoice downloads — all data-controller responsibilities.
    """
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    stripe = _stripe()
    org_id = _org(ctx)
    _, member = ctx
    if member.role != OrgRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the organization owner can manage billing")
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

    # Payload size cap — Stripe events are well under 100 KB in practice.
    # Anything larger is either malicious or a platform bug; reject fast
    # before spending CPU on HMAC verification.
    if len(payload) > 256 * 1024:
        log.warning("stripe webhook: payload too large (%d bytes)", len(payload))
        raise HTTPException(status_code=413, detail="Payload too large")

    # ── 1. Verify signature (RULE 9 — NEVER skip) ────────────────────────────
    # construct_event enforces a 5-minute timestamp tolerance by default,
    # which gives us replay protection in addition to the idempotency
    # check below.
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
    # Insert-first pattern with ON CONFLICT DO NOTHING so two concurrent
    # deliveries of the same event_id can never both pass the check and
    # both process. Only the INSERT that actually wrote the row proceeds.
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    ins = (
        pg_insert(StripeProcessedEvent.__table__)
        .values(event_id=event_id)
        .on_conflict_do_nothing(index_elements=["event_id"])
    )
    result = await db.execute(ins)
    if result.rowcount == 0:
        log.info("stripe webhook: duplicate event ignored", extra={"event_id": event_id})
        await db.commit()  # release the row-lock / transaction
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
                    await log_action(
                        db,
                        action="billing.plan_upgraded",
                        org_id=org.id,
                        target_type="organization",
                        target_id=str(org.id),
                        extra={"event_id": event_id, "stripe_customer": customer_id, "plan": "PRO"},
                    )

        elif event_type in ("customer.subscription.deleted", "customer.subscription.paused"):
            customer_id = event["data"]["object"].get("customer")
            if customer_id:
                org = await db.scalar(
                    select(Organization).where(Organization.stripe_customer_id == customer_id)
                )
                if org:
                    org.plan = OrgPlan.FREE  # ← enum, not raw string
                    log.info("org downgraded to FREE", extra={"stripe_customer": customer_id, "event_id": event_id})
                    await log_action(
                        db,
                        action="billing.plan_downgraded",
                        org_id=org.id,
                        target_type="organization",
                        target_id=str(org.id),
                        extra={"event_id": event_id, "stripe_customer": customer_id, "plan": "FREE", "reason": event_type},
                    )

        elif event_type == "customer.subscription.resumed":
            # An owner who previously paused their subscription (handled
            # above as a downgrade to FREE) has now resumed billing via
            # the Stripe customer portal. Without this branch the org
            # stays on FREE — and thus hits plan-gate 402s on every
            # PRO-only endpoint — while Stripe quietly resumes charging
            # them the PRO price every month. Mirror the upgrade side
            # of the pause/resume symmetry.
            sub_obj = event["data"]["object"]
            customer_id = sub_obj.get("customer")
            sub_status = sub_obj.get("status")
            if customer_id and sub_status in ("active", "trialing"):
                org = await db.scalar(
                    select(Organization).where(Organization.stripe_customer_id == customer_id)
                )
                if org and org.plan != OrgPlan.PRO:
                    org.plan = OrgPlan.PRO
                    log.info(
                        "org restored to PRO after subscription resume",
                        extra={"stripe_customer": customer_id, "event_id": event_id},
                    )
                    await log_action(
                        db,
                        action="billing.plan_upgraded",
                        org_id=org.id,
                        target_type="organization",
                        target_id=str(org.id),
                        extra={
                            "event_id": event_id,
                            "stripe_customer": customer_id,
                            "plan": "PRO",
                            "reason": "subscription.resumed",
                        },
                    )
                    # Recover any active grace period
                    from app.services.grace_period import recover_grace_period
                    await recover_grace_period(db, org.id)

        elif event_type == "invoice.payment_failed":
            invoice_obj = event["data"]["object"]
            customer_id = invoice_obj.get("customer")
            invoice_id = invoice_obj.get("id")
            amount_due = invoice_obj.get("amount_due")
            failure_msg = invoice_obj.get("last_finalization_error", {}).get("message", "Payment failed") if isinstance(invoice_obj.get("last_finalization_error"), dict) else "Payment failed"

            org = await db.scalar(
                select(Organization).where(Organization.stripe_customer_id == customer_id)
            )
            if org:
                from app.services.grace_period import start_grace_period, recover_grace_period
                grace = await start_grace_period(
                    db,
                    org_id=org.id,
                    failed_invoice_id=invoice_id,
                    failed_amount_cents=amount_due,
                    failure_reason=failure_msg,
                )
                log.warning(
                    "stripe invoice payment failed — grace period started",
                    extra={
                        "stripe_customer": customer_id,
                        "event_id": event_id,
                        "grace_expires_at": grace.expires_at.isoformat(),
                    },
                )
            else:
                log.warning("stripe invoice.payment_failed for unknown customer", extra={"stripe_customer": customer_id, "event_id": event_id})

        else:
            log.debug("stripe webhook: unhandled event type", extra={"event_type": event_type})

    except HTTPException:
        raise
    except Exception as e:
        log.error("stripe webhook: processing error", extra={"event_id": event_id, "event_type": event_type, "error": str(e)})
        # Roll back so the idempotency row isn't committed — Stripe will
        # retry and we'll have a fresh attempt.
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

    await db.commit()

    return {"received": True}


# ── Subscription pause / resume ───────────────────────────────────────────────

class PauseStatusOut(BaseModel):
    is_paused: bool
    paused_at: datetime | None
    pause_ends_at: datetime | None
    pause_reminder_sent_at: datetime | None
    days_remaining: int | None


class PauseHistoryOut(BaseModel):
    id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None
    scheduled_resume_at: datetime
    reason: str | None
    resume_reason: str | None
    actor_user_id: uuid.UUID | None
    model_config = {"from_attributes": True}


class PauseCreate(BaseModel):
    days: int = Field(..., ge=1, le=90, description="Number of days to pause (1–90)")
    reason: str | None = Field(None, max_length=128)


@router.get("/pause/status", response_model=PauseStatusOut)
async def get_pause_status(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return whether the subscription is currently paused and when it resumes."""
    org_id = _org(ctx)
    try:
        org = await db.get(Organization, org_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        days_remaining: int | None = None
        if org.is_paused and org.pause_ends_at:
            delta = org.pause_ends_at - datetime.now(timezone.utc)
            days_remaining = max(0, delta.days)
        return PauseStatusOut(
            is_paused=bool(org.is_paused),
            paused_at=org.paused_at,
            pause_ends_at=org.pause_ends_at,
            pause_reminder_sent_at=org.pause_reminder_sent_at,
            days_remaining=days_remaining,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"get_pause_status failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/pause/history", response_model=list[PauseHistoryOut])
async def get_pause_history(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return the last 50 pause windows for this organisation."""
    org_id = _org(ctx)
    try:
        result = await db.execute(
            select(SubscriptionPause)
            .where(SubscriptionPause.org_id == org_id)
            .order_by(SubscriptionPause.started_at.desc())
            .limit(50)
        )
        return result.scalars().all()
    except Exception as e:
        log.error(f"get_pause_history failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/pause", status_code=200)
async def pause_subscription(
    body: PauseCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Pause the subscription for 1–90 days. Owner/Admin only."""
    _, member = ctx
    if member.role not in (OrgRole.OWNER, OrgRole.ADMIN):
        raise HTTPException(status_code=403, detail="Owner or Admin required")
    org_id = _org(ctx)
    try:
        org = await db.get(Organization, org_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        if org.is_paused:
            raise HTTPException(status_code=409, detail="Subscription is already paused")
        now = datetime.now(timezone.utc)
        scheduled_resume = now + timedelta(days=body.days)
        org.is_paused = True
        org.paused_at = now
        org.pause_ends_at = scheduled_resume
        pause_row = SubscriptionPause(
            org_id=org_id,
            scheduled_resume_at=scheduled_resume,
            reason=body.reason,
            actor_user_id=member.user_id,
        )
        db.add(pause_row)
        await db.commit()
        await log_action(
            db,
            action="billing.pause",
            org_id=org_id,
            target_type="organization",
            target_id=str(org_id),
            extra={"days": body.days, "reason": body.reason},
        )
        return {"ok": True, "resume_at": scheduled_resume.isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"pause_subscription failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/resume", status_code=200)
async def resume_subscription(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Resume a paused subscription immediately. Owner/Admin only."""
    _, member = ctx
    if member.role not in (OrgRole.OWNER, OrgRole.ADMIN):
        raise HTTPException(status_code=403, detail="Owner or Admin required")
    org_id = _org(ctx)
    try:
        org = await db.get(Organization, org_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        if not org.is_paused:
            raise HTTPException(status_code=409, detail="Subscription is not paused")
        now = datetime.now(timezone.utc)
        org.is_paused = False
        org.paused_at = None
        org.pause_ends_at = None
        active_row = await db.scalar(
            select(SubscriptionPause)
            .where(
                SubscriptionPause.org_id == org_id,
                SubscriptionPause.ended_at.is_(None),
            )
            .limit(1)
        )
        if active_row:
            active_row.ended_at = now
            active_row.resume_reason = "manual"
        await db.commit()
        await log_action(
            db,
            action="billing.resume",
            org_id=org_id,
            target_type="organization",
            target_id=str(org_id),
            extra={},
        )
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"resume_subscription failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
