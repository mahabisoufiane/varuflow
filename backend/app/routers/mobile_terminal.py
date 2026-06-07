"""Stripe Terminal — NFC / tap-to-pay mobile POS

Uses Stripe Terminal SDK. The frontend generates a connection token,
then uses the Terminal JS/React Native SDK to interact with a reader.
The backend:
  1. Issues connection tokens (required by Terminal SDK)
  2. Creates PaymentIntents for Terminal collection
  3. Records results in StripeTerminalSession

Endpoints:
  POST /api/mobile/terminal/connection-token
  POST /api/mobile/terminal/create-payment
  POST /api/mobile/terminal/capture/{payment_intent_id}
  POST /api/mobile/terminal/cancel/{payment_intent_id}
  GET  /api/mobile/terminal/sessions
  GET  /api/mobile/terminal/readers            (list registered readers)
"""
from __future__ import annotations

import logging
import os
import uuid
from decimal import Decimal
from typing import Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.invoicing import Invoice, InvoiceStatus
from app.models.mobile_field import StripeTerminalSession
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/mobile/terminal", tags=["mobile_terminal"], dependencies=[Depends(require_module("pos"))])
log = logging.getLogger(__name__)


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _stripe_key() -> str:
    key = os.getenv("STRIPE_SECRET_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Stripe not configured")
    return key


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreatePaymentIn(BaseModel):
    amount: Decimal                # in major currency units (e.g. 120.50 SEK)
    currency: str = "sek"
    invoice_id: Optional[uuid.UUID] = None
    reader_id: Optional[str] = None   # Stripe Terminal reader ID
    description: Optional[str] = None

class SessionOut(BaseModel):
    id: str
    reader_id: Optional[str]
    payment_intent_id: Optional[str]
    invoice_id: Optional[str]
    amount: str
    currency: str
    status: str
    created_at: str

class SessionsOut(BaseModel):
    sessions: list[SessionOut]
    total: int


def _sess_out(s: StripeTerminalSession) -> SessionOut:
    return SessionOut(
        id=str(s.id),
        reader_id=s.reader_id,
        payment_intent_id=s.payment_intent_id,
        invoice_id=str(s.invoice_id) if s.invoice_id else None,
        amount=str(s.amount),
        currency=s.currency,
        status=s.status,
        created_at=s.created_at.isoformat(),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/connection-token")
async def create_connection_token(
    ctx: tuple = Depends(get_current_member),
):
    """Issue a Stripe Terminal connection token for the SDK."""
    org_id = _org(ctx)
    try:
        stripe.api_key = _stripe_key()
        token = stripe.terminal.ConnectionToken.create()
        return {"secret": token.secret}
    except stripe.error.StripeError as e:
        log.error("terminal_connection_token failed: %s", str(e), extra={"org_id": str(org_id)})  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
        raise HTTPException(status_code=502, detail=f"Stripe error: {e.user_message or str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        log.error("terminal_connection_token failed: %s", str(e), extra={"org_id": str(org_id)})  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/create-payment", response_model=SessionOut)
async def create_terminal_payment(
    body: CreatePaymentIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Create a PaymentIntent for Terminal collection (reader will present card prompt)."""
    org_id = _org(ctx)
    try:
        stripe.api_key = _stripe_key()

        # Validate invoice if provided
        if body.invoice_id:
            inv_row = await db.execute(
                select(Invoice).where(Invoice.id == body.invoice_id, Invoice.org_id == org_id)
            )
            if not inv_row.scalar_one_or_none():
                raise HTTPException(status_code=404, detail="Invoice not found")

        # Stripe amounts are in minor units (öre for SEK)
        amount_minor = int(body.amount * 100)
        pi = stripe.PaymentIntent.create(
            amount=amount_minor,
            currency=body.currency.lower(),
            payment_method_types=["card_present"],
            capture_method="manual",  # Terminal requires manual capture
            description=body.description or "Varuflow Terminal payment",
        )

        # Present to reader if reader_id supplied
        if body.reader_id:
            try:
                stripe.terminal.Reader.process_payment_intent(
                    body.reader_id,
                    payment_intent=pi.id,
                )
            except stripe.error.StripeError as e:
                log.warning("terminal reader process failed: %s", str(e))

        session = StripeTerminalSession(
            org_id=org_id,
            reader_id=body.reader_id,
            payment_intent_id=pi.id,
            invoice_id=body.invoice_id,
            amount=body.amount,
            currency=body.currency.upper(),
            status="initiated",
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return _sess_out(session)
    except HTTPException:
        raise
    except stripe.error.StripeError as e:
        log.error("create_terminal_payment stripe error: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=502, detail=f"Stripe error: {e.user_message or str(e)}")
    except Exception as e:
        log.error("create_terminal_payment failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/capture/{payment_intent_id}", response_model=SessionOut)
async def capture_payment(
    payment_intent_id: str,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Capture the payment after card is presented to reader."""
    org_id = _org(ctx)
    try:
        stripe.api_key = _stripe_key()

        row = await db.execute(
            select(StripeTerminalSession).where(
                StripeTerminalSession.payment_intent_id == payment_intent_id,
                StripeTerminalSession.org_id == org_id,
            )
        )
        session = row.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Terminal session not found")

        pi = stripe.PaymentIntent.capture(payment_intent_id)
        session.status = "succeeded" if pi.status == "succeeded" else "processing"
        session.stripe_response = {"status": pi.status, "id": pi.id}

        # Mark corresponding invoice paid
        if session.invoice_id and session.status == "succeeded":
            inv_row = await db.execute(select(Invoice).where(Invoice.id == session.invoice_id))
            invoice = inv_row.scalar_one_or_none()
            if invoice and invoice.status != InvoiceStatus.PAID:
                invoice.status = InvoiceStatus.PAID

        await db.commit()
        await db.refresh(session)
        return _sess_out(session)
    except HTTPException:
        raise
    except stripe.error.StripeError as e:
        log.error("capture_payment stripe error: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=502, detail=f"Stripe error: {e.user_message or str(e)}")
    except Exception as e:
        log.error("capture_payment failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/cancel/{payment_intent_id}", response_model=SessionOut)
async def cancel_payment(
    payment_intent_id: str,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        stripe.api_key = _stripe_key()

        row = await db.execute(
            select(StripeTerminalSession).where(
                StripeTerminalSession.payment_intent_id == payment_intent_id,
                StripeTerminalSession.org_id == org_id,
            )
        )
        session = row.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Terminal session not found")

        stripe.PaymentIntent.cancel(payment_intent_id)
        session.status = "canceled"
        await db.commit()
        await db.refresh(session)
        return _sess_out(session)
    except HTTPException:
        raise
    except stripe.error.StripeError as e:
        log.error("cancel_payment stripe error: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=502, detail=f"Stripe error: {e.user_message or str(e)}")
    except Exception as e:
        log.error("cancel_payment failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/sessions", response_model=SessionsOut)
async def list_sessions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        count_row = await db.execute(
            select(func.count(StripeTerminalSession.id)).where(StripeTerminalSession.org_id == org_id)
        )
        total = count_row.scalar_one() or 0
        rows = await db.execute(
            select(StripeTerminalSession)
            .where(StripeTerminalSession.org_id == org_id)
            .order_by(StripeTerminalSession.created_at.desc())
            .limit(limit).offset((page - 1) * limit)
        )
        return SessionsOut(sessions=[_sess_out(s) for s in rows.scalars()], total=total)
    except Exception as e:
        log.error("list_terminal_sessions failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/readers")
async def list_readers(
    ctx: tuple = Depends(get_current_member),
):
    """List registered Stripe Terminal readers for this Stripe account."""
    org_id = _org(ctx)
    try:
        stripe.api_key = _stripe_key()
        readers = stripe.terminal.Reader.list(limit=20)
        return {
            "readers": [
                {
                    "id": r.id,
                    "label": r.label,
                    "device_type": r.device_type,
                    "status": r.status,
                    "location": r.location,
                }
                for r in readers.data
            ]
        }
    except stripe.error.StripeError as e:
        log.error("list_readers stripe error: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=502, detail=f"Stripe error: {e.user_message or str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_readers failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
