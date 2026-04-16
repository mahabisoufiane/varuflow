from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

router = APIRouter(tags=["health"])


class SystemStatusResponse(BaseModel):
    """Public capability probe. Returns only booleans — no secrets, no tenant
    data — so the frontend can hide disabled flows (Upgrade, Send invoice
    email, Connect Fortnox, AI chat) instead of letting users click into 503s."""
    # Billing (Stripe)
    stripe_configured:                bool
    billing_checkout_available:       bool
    billing_portal_available:         bool
    invoice_payment_links_available:  bool
    # Accounting (Fortnox OAuth)
    fortnox_configured:               bool
    # Email delivery
    transactional_email_available:    bool   # Resend (customer-facing invoice/reminder emails)
    auth_email_available:             bool   # SMTP or Resend (password reset, magic link)
    # AI
    ai_chat_available:                bool   # GPT-4o in integrations.py
    # Observability
    error_tracking_enabled:           bool   # Sentry
    # Country routing
    default_country:                  str


@router.get("/system/status", response_model=SystemStatusResponse)
async def system_status() -> SystemStatusResponse:
    """Report which optional integrations are active in this deployment."""
    has_stripe_secret  = bool(settings.STRIPE_SECRET_KEY)
    has_stripe_webhook = bool(settings.STRIPE_WEBHOOK_SECRET)
    has_stripe_price   = bool(getattr(settings, "STRIPE_PRO_PRICE_ID", ""))
    has_resend         = bool(settings.RESEND_API_KEY)
    has_smtp           = bool(settings.SMTP_HOST)
    return SystemStatusResponse(
        stripe_configured               = has_stripe_secret,
        billing_checkout_available      = has_stripe_secret and has_stripe_price,
        billing_portal_available        = has_stripe_secret,
        invoice_payment_links_available = has_stripe_secret and has_stripe_webhook,
        fortnox_configured              = bool(settings.FORTNOX_CLIENT_ID and settings.FORTNOX_CLIENT_SECRET),
        transactional_email_available   = has_resend,
        auth_email_available            = has_resend or has_smtp,
        ai_chat_available               = bool(settings.OPENAI_API_KEY),
        error_tracking_enabled          = bool(settings.SENTRY_DSN),
        default_country                 = getattr(settings, "DEFAULT_COUNTRY", "SE"),
    )


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    status = "ok" if db_status == "ok" else "degraded"
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=200 if status == "ok" else 503,
        content={"status": status, "version": "0.1.0", "database": db_status},
    )


@router.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"status": "error", "database": "disconnected"})
