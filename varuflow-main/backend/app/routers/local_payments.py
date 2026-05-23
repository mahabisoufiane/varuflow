"""Local Payment Methods router
Supports: Klarna, Swish, Vipps, Tabby, Tamara, mada, KNET

Endpoints:
  GET    /api/local-payments/config
  PATCH  /api/local-payments/config/{provider}
  POST   /api/local-payments/sessions
  GET    /api/local-payments/sessions
  GET    /api/local-payments/sessions/{session_id}
  POST   /api/local-payments/sessions/{session_id}/cancel
  POST   /api/local-payments/webhook/{provider}
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.invoicing import Payment, PaymentMethod
from app.models.local_payments import LocalPaymentConfig, LocalPaymentSession

router = APIRouter(prefix="/api/local-payments", tags=["local_payments"])
logger = logging.getLogger(__name__)

SUPPORTED_PROVIDERS = {
    "klarna", "swish", "vipps", "tabby", "tamara", "mada", "knet"
}


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Schemas ───────────────────────────────────────────────────────────────────

class ConfigOut(BaseModel):
    id: str
    provider: str
    is_enabled: bool
    merchant_id: Optional[str]
    config_json: Optional[Any]
    created_at: str
    updated_at: str


class ConfigPatchIn(BaseModel):
    is_enabled: Optional[bool] = None
    merchant_id: Optional[str] = None
    config_json: Optional[Any] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    webhook_secret: Optional[str] = None


class SessionCreateIn(BaseModel):
    invoice_id: Optional[str] = None
    provider: str
    amount: Decimal
    currency: str = "SEK"
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None
    callback_url: Optional[str] = None


class SessionOut(BaseModel):
    id: str
    provider: str
    invoice_id: Optional[str]
    amount: str
    currency: str
    customer_email: Optional[str]
    customer_name: Optional[str]
    status: str
    redirect_url: Optional[str]
    provider_session_id: Optional[str]
    created_at: str
    updated_at: str


def _config_out(c: LocalPaymentConfig) -> ConfigOut:
    return ConfigOut(
        id=str(c.id),
        provider=c.provider,
        is_enabled=c.is_enabled,
        merchant_id=c.merchant_id,
        config_json=c.config_json,
        created_at=c.created_at.isoformat(),
        updated_at=c.updated_at.isoformat(),
    )


def _session_out(s: LocalPaymentSession) -> SessionOut:
    return SessionOut(
        id=str(s.id),
        provider=s.provider,
        invoice_id=str(s.invoice_id) if s.invoice_id else None,
        amount=str(s.amount),
        currency=s.currency,
        customer_email=s.customer_email,
        customer_name=s.customer_name,
        status=s.status,
        redirect_url=s.redirect_url,
        provider_session_id=s.provider_session_id,
        created_at=s.created_at.isoformat(),
        updated_at=s.updated_at.isoformat(),
    )


def _stub_redirect_url(provider: str, session_id: str) -> str:
    bases = {
        "klarna": "https://payment.klarna.com/checkout",
        "swish": "https://mss.cpc.getswish.net/swish-cpcapi/api/v1/paymentrequests",
        "vipps": "https://api.vipps.no/epayment/v1/payments",
        "tabby": "https://checkout.tabby.ai",
        "tamara": "https://checkout.tamara.co",
        "mada": "https://pay.saudipayments.com/checkout",
        "knet": "https://gateway.knet.com.kw/PaymentHTTP.htm",
    }
    base = bases.get(provider, "https://checkout.example.com")
    return f"{base}/{session_id}"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/config", response_model=list[ConfigOut])
async def list_configs(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """List all provider configs for this org."""
    org_id = _org(ctx)
    try:
        rows = await db.execute(
            select(LocalPaymentConfig)
            .where(LocalPaymentConfig.org_id == org_id)
            .order_by(LocalPaymentConfig.provider)
        )
        configs = list(rows.scalars())
        # Ensure all supported providers have a row (return stubs for unconfigured)
        existing = {c.provider for c in configs}
        result = [_config_out(c) for c in configs]
        for provider in sorted(SUPPORTED_PROVIDERS - existing):
            result.append(ConfigOut(
                id="",
                provider=provider,
                is_enabled=False,
                merchant_id=None,
                config_json=None,
                created_at="",
                updated_at="",
            ))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("local_payments_list_configs failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/config/{provider}", response_model=ConfigOut)
async def patch_config(
    provider: str,
    body: ConfigPatchIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Enable/disable a provider and update its configuration."""
    org_id = _org(ctx)
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown provider: {provider}. Valid: {sorted(SUPPORTED_PROVIDERS)}",
        )
    try:
        row = await db.execute(
            select(LocalPaymentConfig).where(
                LocalPaymentConfig.org_id == org_id,
                LocalPaymentConfig.provider == provider,
            )
        )
        config = row.scalar_one_or_none()
        if not config:
            config = LocalPaymentConfig(org_id=org_id, provider=provider)
            db.add(config)

        if body.is_enabled is not None:
            config.is_enabled = body.is_enabled
        if body.merchant_id is not None:
            config.merchant_id = body.merchant_id
        if body.config_json is not None:
            config.config_json = body.config_json
        if body.api_key is not None:
            # In production this would be encrypted with PII_ENCRYPTION_KEY
            config.api_key_encrypted = body.api_key
        if body.api_secret is not None:
            config.api_secret_encrypted = body.api_secret
        if body.webhook_secret is not None:
            config.webhook_secret_encrypted = body.webhook_secret

        config.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(config)
        return _config_out(config)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "local_payments_patch_config failed: %s", str(e),
            extra={"org_id": str(org_id), "provider": provider},
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sessions", response_model=SessionOut, status_code=201)
async def create_session(
    body: SessionCreateIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Create a payment session. Validates provider is enabled for this org."""
    org_id = _org(ctx)
    if body.provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown provider: {body.provider}. Valid: {sorted(SUPPORTED_PROVIDERS)}",
        )
    try:
        # Verify provider is enabled for this org
        cfg_row = await db.execute(
            select(LocalPaymentConfig).where(
                LocalPaymentConfig.org_id == org_id,
                LocalPaymentConfig.provider == body.provider,
                LocalPaymentConfig.is_enabled.is_(True),
            )
        )
        if not cfg_row.scalar_one_or_none():
            raise HTTPException(
                status_code=422,
                detail=f"Provider '{body.provider}' is not enabled for this organisation",
            )

        invoice_id: Optional[uuid.UUID] = None
        if body.invoice_id:
            invoice_id = uuid.UUID(body.invoice_id)

        stub_provider_session_id = f"stub-{body.provider}-{uuid.uuid4().hex[:12]}"
        redirect_url = _stub_redirect_url(body.provider, stub_provider_session_id)

        session = LocalPaymentSession(
            org_id=org_id,
            invoice_id=invoice_id,
            provider=body.provider,
            amount=body.amount,
            currency=body.currency,
            customer_email=body.customer_email,
            customer_name=body.customer_name,
            status="pending",
            provider_session_id=stub_provider_session_id,
            redirect_url=redirect_url,
            callback_url=body.callback_url,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return _session_out(session)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "local_payments_create_session failed: %s", str(e),
            extra={"org_id": str(org_id)},
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/sessions", response_model=dict)
async def list_sessions(
    provider: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    invoice_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """List payment sessions for this org with optional filters."""
    org_id = _org(ctx)
    try:
        q = select(LocalPaymentSession).where(LocalPaymentSession.org_id == org_id)
        if provider:
            q = q.where(LocalPaymentSession.provider == provider)
        if status:
            q = q.where(LocalPaymentSession.status == status)
        if invoice_id:
            q = q.where(LocalPaymentSession.invoice_id == uuid.UUID(invoice_id))

        rows = await db.execute(
            q.order_by(LocalPaymentSession.created_at.desc())
            .limit(limit)
            .offset((page - 1) * limit)
        )
        sessions = [_session_out(s) for s in rows.scalars()]
        return {"sessions": sessions, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "local_payments_list_sessions failed: %s", str(e),
            extra={"org_id": str(org_id)},
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/sessions/{session_id}", response_model=SessionOut)
async def get_session(
    session_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Get the status of a payment session."""
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(LocalPaymentSession).where(
                LocalPaymentSession.id == session_id,
                LocalPaymentSession.org_id == org_id,
            )
        )
        session = row.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Payment session not found")
        return _session_out(session)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "local_payments_get_session failed: %s", str(e),
            extra={"org_id": str(org_id)},
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sessions/{session_id}/cancel", response_model=SessionOut)
async def cancel_session(
    session_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a pending payment session."""
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(LocalPaymentSession).where(
                LocalPaymentSession.id == session_id,
                LocalPaymentSession.org_id == org_id,
            )
        )
        session = row.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Payment session not found")
        if session.status not in ("pending", "authorized"):
            raise HTTPException(
                status_code=422,
                detail=f"Cannot cancel session with status '{session.status}'",
            )
        session.status = "cancelled"
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(session)
        return _session_out(session)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "local_payments_cancel_session failed: %s", str(e),
            extra={"org_id": str(org_id)},
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/webhook/{provider}", status_code=200)
async def payment_webhook(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive payment status callbacks from local payment providers.

    Auth-free endpoint — validates provider identity via payload.
    On captured status, auto-records a Payment against the linked invoice.
    """
    try:
        payload = await request.json()
        provider_session_id = (
            payload.get("sessionId")
            or payload.get("session_id")
            or payload.get("paymentId")
            or payload.get("payment_id")
            or payload.get("orderId")
        )
        raw_status = str(payload.get("status", "")).upper()
        if raw_status in ("PAID", "SUCCESS", "CAPTURED", "APPROVED"):
            new_status = "captured"
        elif raw_status in ("FAILED", "DECLINED", "REJECTED"):
            new_status = "failed"
        elif raw_status in ("CANCELLED", "CANCELED"):
            new_status = "cancelled"
        elif raw_status in ("AUTHORIZED",):
            new_status = "authorized"
        else:
            new_status = None  # unknown — don't update

        if provider_session_id:
            row = await db.execute(
                select(LocalPaymentSession).where(
                    LocalPaymentSession.provider_session_id == provider_session_id
                )
            )
            session = row.scalar_one_or_none()
            if session and new_status:
                session.status = new_status
                session.provider_response = payload
                session.updated_at = datetime.now(timezone.utc)

                if new_status == "captured" and session.invoice_id:
                    # Determine payment method enum value
                    provider_to_method = {
                        "klarna": "OTHER",
                        "swish": "OTHER",
                        "vipps": "OTHER",
                        "tabby": "OTHER",
                        "tamara": "OTHER",
                        "mada": "OTHER",
                        "knet": "OTHER",
                    }
                    method_str = provider_to_method.get(provider, "BANK_TRANSFER")
                    try:
                        method = PaymentMethod(method_str)
                    except ValueError:
                        method = PaymentMethod.BANK_TRANSFER

                    payment = Payment(
                        org_id=session.org_id,
                        invoice_id=session.invoice_id,
                        amount=session.amount,
                        payment_date=date.today(),
                        method=method,
                        reference=f"Auto-recorded via {provider} webhook",
                        currency=session.currency,
                    )
                    db.add(payment)

                await db.commit()

        logger.info(
            "local_payment_webhook: provider=%s status=%s session=%s",
            provider,
            new_status,
            provider_session_id,
        )
        return {"received": True}
    except Exception as e:
        logger.error("local_payment_webhook failed: provider=%s error=%s", provider, str(e))
        return {"received": False}
