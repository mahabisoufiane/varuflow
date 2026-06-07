"""Wallet payment sessions (Apple Pay / Google Pay via Stripe) — Sprint 10.

Endpoints under ``/api/wallet-payments``:

    GET    ""               list sessions (filter by customer_id, status)
    POST   ""               initiate session
    POST   /{id}/complete   mark completed
    POST   /{id}/fail       mark failed
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.wallet_payment_session import WalletPaymentSession
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/wallet-payments", tags=["wallet-payments"], dependencies=[Depends(require_module("pos"))])
logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────────────

class WalletSessionCreate(BaseModel):
    customer_id: uuid.UUID
    invoice_id: uuid.UUID | None = None
    amount: Decimal
    currency: str = "SEK"
    provider: str  # "apple_pay" | "google_pay" | "stripe"
    provider_session_id: str | None = None


class WalletSessionOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    invoice_id: uuid.UUID | None
    amount: Decimal
    currency: str
    provider: str
    status: str
    provider_session_id: str | None
    completed_at: datetime | None
    created_at: datetime


def _to_out(row: WalletPaymentSession) -> WalletSessionOut:
    return WalletSessionOut(
        id=row.id,
        org_id=row.org_id,
        customer_id=row.customer_id,
        invoice_id=row.invoice_id,
        amount=row.amount,
        currency=row.currency,
        provider=row.provider,
        status=row.status,
        provider_session_id=row.provider_session_id,
        completed_at=row.completed_at,
        created_at=row.created_at,
    )


async def _load(db: AsyncSession, *, session_id: uuid.UUID, org_id: uuid.UUID) -> WalletPaymentSession:
    row = await db.get(WalletPaymentSession, session_id)
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Wallet session not found")
    return row


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[WalletSessionOut])
async def list_sessions(
    customer_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        stmt = select(WalletPaymentSession).where(WalletPaymentSession.org_id == member.org_id)
        if customer_id is not None:
            stmt = stmt.where(WalletPaymentSession.customer_id == customer_id)
        if status is not None:
            stmt = stmt.where(WalletPaymentSession.status == status)
        stmt = stmt.order_by(WalletPaymentSession.created_at.desc()).limit(limit).offset(offset)
        rows = (await db.scalars(stmt)).all()
        return [_to_out(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_wallet_sessions failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=WalletSessionOut, status_code=201)
async def initiate_session(
    body: WalletSessionCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        row = WalletPaymentSession(
            org_id=member.org_id,
            customer_id=body.customer_id,
            invoice_id=body.invoice_id,
            amount=body.amount,
            currency=body.currency,
            provider=body.provider,
            status="pending",
            provider_session_id=body.provider_session_id,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _to_out(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"initiate_wallet_session failed: {str(e)}", extra={"org_id": str(member.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{session_id}/complete", response_model=WalletSessionOut)
async def complete_session(
    session_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        row = await _load(db, session_id=session_id, org_id=member.org_id)
        row.status = "completed"
        row.completed_at = datetime.now(tz=timezone.utc)
        await db.commit()
        await db.refresh(row)
        return _to_out(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"complete_wallet_session failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{session_id}/fail", response_model=WalletSessionOut)
async def fail_session(
    session_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        row = await _load(db, session_id=session_id, org_id=member.org_id)
        row.status = "failed"
        await db.commit()
        await db.refresh(row)
        return _to_out(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"fail_wallet_session failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
