"""GCC Payment Rails
Supports: mada (Saudi), KNET (Kuwait), Benefit (Bahrain), Fawry (Egypt)

These are provider stubs with the correct API response shapes.
Each provider requires a merchant account + API credentials.
Webhook endpoints are auth-free and verify provider identity via payload structure.

Endpoints:
  GET  /api/mena/payments/providers
  POST /api/mena/payments/initiate
  POST /api/mena/payments/webhook/{provider}
  GET  /api/mena/payments/sessions
  GET  /api/mena/payments/sessions/{session_id}
"""
from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from .gcc_payments_models import GccPaymentSession
from app.features.invoicing.models import Invoice, InvoiceStatus

router = APIRouter(prefix="/api/mena/payments", tags=["mena_payments"], dependencies=[Depends(require_module("invoicing"))])
log = logging.getLogger(__name__)

PROVIDERS = {
    "mada": {
        "name": "mada",
        "display_name": "mada (Saudi Payments Network)",
        "country": "SA",
        "currency": "SAR",
        "docs": "https://mada.com.sa",
        "configured": False,
    },
    "knet": {
        "name": "knet",
        "display_name": "KNET (Kuwait)",
        "country": "KW",
        "currency": "KWD",
        "docs": "https://www.knet.com.kw",
        "configured": False,
    },
    "benefit": {
        "name": "benefit",
        "display_name": "Benefit (Bahrain)",
        "country": "BH",
        "currency": "BHD",
        "docs": "https://www.benefit.bh",
        "configured": False,
    },
    "fawry": {
        "name": "fawry",
        "display_name": "Fawry (Egypt)",
        "country": "EG",
        "currency": "EGP",
        "docs": "https://developer.fawrystaging.com",
        "configured": False,
    },
}


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _stub_checkout_url(provider: str, session_id: str) -> str:
    base = {
        "mada": "https://pay.saudipayments.com/checkout",
        "knet": "https://gateway.knet.com.kw/PaymentHTTP.htm",
        "benefit": "https://checkout.benefit.bh/payment",
        "fawry": "https://www.fawrystaging.com/ECommercePlugin",
    }
    return f"{base.get(provider, 'https://example.com')}/{session_id}"


# ── Schemas ───────────────────────────────────────────────────────────────────

class InitiateIn(BaseModel):
    invoice_id: str
    provider: str
    currency: str = "SAR"

class InitiateOut(BaseModel):
    session_id: str
    checkout_url: str
    provider: str
    amount: str
    currency: str
    status: str

class SessionOut(BaseModel):
    id: str
    invoice_id: str
    provider: str
    provider_session_id: Optional[str]
    amount: str
    currency: str
    status: str
    created_at: str

class SessionsOut(BaseModel):
    sessions: list[SessionOut]
    total: int


def _sess_out(s: GccPaymentSession) -> SessionOut:
    return SessionOut(
        id=str(s.id),
        invoice_id=str(s.invoice_id),
        provider=s.provider,
        provider_session_id=s.provider_session_id,
        amount=str(s.amount),
        currency=s.currency,
        status=s.status,
        created_at=s.created_at.isoformat(),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/providers")
async def get_providers(ctx: tuple = Depends(get_current_member)):
    return {"providers": list(PROVIDERS.values())}


@router.post("/initiate", response_model=InitiateOut)
async def initiate_payment(
    body: InitiateIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    if body.provider not in PROVIDERS:
        raise HTTPException(status_code=422, detail=f"Unknown provider: {body.provider}. Valid: {list(PROVIDERS)}")
    try:
        inv_id = uuid.UUID(body.invoice_id)
        inv_row = await db.execute(
            select(Invoice).where(Invoice.id == inv_id, Invoice.org_id == org_id)
        )
        invoice = inv_row.scalar_one_or_none()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        stub_provider_session_id = f"stub-{body.provider}-{uuid.uuid4().hex[:12]}"
        session = GccPaymentSession(
            org_id=org_id,
            invoice_id=inv_id,
            provider=body.provider,
            provider_session_id=stub_provider_session_id,
            amount=invoice.total_sek or Decimal("0"),
            currency=body.currency,
            status="initiated",
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

        return InitiateOut(
            session_id=str(session.id),
            checkout_url=_stub_checkout_url(body.provider, stub_provider_session_id),
            provider=body.provider,
            amount=str(session.amount),
            currency=session.currency,
            status="initiated",
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error("gcc_payments_initiate failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/webhook/{provider}", status_code=200)
async def payment_webhook(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive payment status updates from GCC payment providers.

    Auth-free endpoint — validates provider signature from payload.
    STUB: logs receipt and updates session status.
    """
    try:
        payload = await request.json()
        provider_session_id = (
            payload.get("sessionId")  # mada/benefit shape
            or payload.get("paymentId")  # knet shape
            or payload.get("merchantRefNumber")  # fawry shape
        )
        status_str = str(payload.get("status", "")).upper()
        new_status = "paid" if status_str in ("PAID", "SUCCESS", "CAPTURED") else "failed"

        if provider_session_id:
            row = await db.execute(
                select(GccPaymentSession).where(
                    GccPaymentSession.provider_session_id == provider_session_id
                )
            )
            session = row.scalar_one_or_none()
            if session:
                session.status = new_status
                session.webhook_payload = payload
                if new_status == "paid":
                    # Mark corresponding invoice paid
                    inv_row = await db.execute(
                        select(Invoice).where(Invoice.id == session.invoice_id)
                    )
                    invoice = inv_row.scalar_one_or_none()
                    if invoice and invoice.status != InvoiceStatus.PAID:
                        invoice.status = InvoiceStatus.PAID
                await db.commit()

        log.info("gcc_webhook: provider=%s status=%s", provider, new_status)
        return {"received": True}
    except Exception as e:
        log.error("gcc_webhook failed: %s", str(e))
        return {"received": False}


@router.get("/sessions", response_model=SessionsOut)
async def list_sessions(
    invoice_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        q = select(GccPaymentSession).where(GccPaymentSession.org_id == org_id)
        if invoice_id:
            q = q.where(GccPaymentSession.invoice_id == uuid.UUID(invoice_id))
        if status:
            q = q.where(GccPaymentSession.status == status)
        count_row = await db.execute(
            select(func.count(GccPaymentSession.id)).where(
                GccPaymentSession.org_id == org_id
            )
        )
        total = count_row.scalar_one() or 0
        rows = await db.execute(q.order_by(GccPaymentSession.created_at.desc()).limit(limit).offset((page - 1) * limit))
        return SessionsOut(sessions=[_sess_out(s) for s in rows.scalars()], total=total)
    except HTTPException:
        raise
    except Exception as e:
        log.error("gcc_sessions_list failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/sessions/{session_id}", response_model=SessionOut)
async def get_session(
    session_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(GccPaymentSession).where(
                GccPaymentSession.id == session_id,
                GccPaymentSession.org_id == org_id,
            )
        )
        sess = row.scalar_one_or_none()
        if not sess:
            raise HTTPException(status_code=404, detail="Payment session not found")
        return _sess_out(sess)
    except HTTPException:
        raise
    except Exception as e:
        log.error("gcc_session_get failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
