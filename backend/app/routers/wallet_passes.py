"""Wallet passes router — issue and manage Apple/Google Wallet loyalty cards.

Endpoints
─────────
GET    /api/wallet                          → list passes for org
POST   /api/wallet                          → issue new pass
GET    /api/wallet/customer/{customer_id}   → all passes for a customer
GET    /api/wallet/{id}                     → detail
POST   /api/wallet/{id}/sync                → refresh points from loyalty account
POST   /api/wallet/{id}/revoke              → revoke pass

NOTE: /customer/{customer_id} is declared BEFORE /{id} to avoid routing conflict.
"""
from __future__ import annotations

import logging
import secrets
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.loyalty import LoyaltyAccount
from app.models.wallet_pass import WalletPass

router = APIRouter(prefix="/api/wallet", tags=["wallet-passes"])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> _uuid.UUID:
    _, member = ctx
    return member.org_id


def _pass_out(p: WalletPass) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "org_id": str(p.org_id),
        "customer_id": str(p.customer_id),
        "pass_type": p.pass_type,
        "platform": p.platform,
        "serial_number": p.serial_number,
        "barcode_value": p.barcode_value,
        "points_balance": p.points_balance,
        "tier": p.tier,
        "last_synced_at": p.last_synced_at.isoformat() if p.last_synced_at else None,
        "revoked": p.revoked,
        "created_at": p.created_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class WalletPassIn(BaseModel):
    customer_id: _uuid.UUID
    platform: str = Field(min_length=1, max_length=20)
    pass_type: str = Field(default="loyalty", max_length=20)
    tier: Optional[str] = Field(default=None, max_length=50)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_wallet_passes(
    platform: Optional[str] = Query(default=None),
    customer_id: Optional[_uuid.UUID] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = select(WalletPass).where(WalletPass.org_id == org_id)
        if platform:
            q = q.where(WalletPass.platform == platform)
        if customer_id:
            q = q.where(WalletPass.customer_id == customer_id)
        q = q.order_by(WalletPass.created_at)
        passes = (await db.execute(q)).scalars().all()
        return [_pass_out(p) for p in passes]
    except Exception as e:
        log.error("list_wallet_passes failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def issue_wallet_pass(
    body: WalletPassIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        # Look up loyalty account for initial points balance
        loyalty = await db.scalar(
            select(LoyaltyAccount).where(
                LoyaltyAccount.org_id == org_id,
                LoyaltyAccount.customer_id == body.customer_id,
            )
        )
        points = loyalty.points_balance if loyalty else 0

        wallet_pass = WalletPass(
            org_id=org_id,
            customer_id=body.customer_id,
            pass_type=body.pass_type,
            platform=body.platform,
            serial_number=secrets.token_hex(16),
            barcode_value=str(_uuid.uuid4()),
            points_balance=points,
            tier=body.tier,
        )
        db.add(wallet_pass)
        await db.commit()
        await db.refresh(wallet_pass)
        return _pass_out(wallet_pass)
    except HTTPException:
        raise
    except Exception as e:
        log.error("issue_wallet_pass failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# Declared before /{pass_id} to avoid routing conflict
@router.get("/customer/{customer_id}")
async def list_passes_for_customer(
    customer_id: _uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        passes = (await db.execute(
            select(WalletPass).where(
                WalletPass.org_id == org_id,
                WalletPass.customer_id == customer_id,
            ).order_by(WalletPass.created_at)
        )).scalars().all()
        return [_pass_out(p) for p in passes]
    except Exception as e:
        log.error("list_passes_for_customer failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{pass_id}")
async def get_wallet_pass(
    pass_id: _uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        wallet_pass = await db.scalar(
            select(WalletPass).where(
                WalletPass.id == pass_id, WalletPass.org_id == org_id
            )
        )
        if not wallet_pass:
            raise HTTPException(status_code=404, detail="Wallet pass not found")
        return _pass_out(wallet_pass)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_wallet_pass failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{pass_id}/sync")
async def sync_wallet_pass(
    pass_id: _uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        wallet_pass = await db.scalar(
            select(WalletPass).where(
                WalletPass.id == pass_id, WalletPass.org_id == org_id
            )
        )
        if not wallet_pass:
            raise HTTPException(status_code=404, detail="Wallet pass not found")

        loyalty = await db.scalar(
            select(LoyaltyAccount).where(
                LoyaltyAccount.org_id == org_id,
                LoyaltyAccount.customer_id == wallet_pass.customer_id,
            )
        )
        if loyalty:
            wallet_pass.points_balance = loyalty.points_balance

        wallet_pass.last_synced_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(wallet_pass)
        return _pass_out(wallet_pass)
    except HTTPException:
        raise
    except Exception as e:
        log.error("sync_wallet_pass failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{pass_id}/revoke")
async def revoke_wallet_pass(
    pass_id: _uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        wallet_pass = await db.scalar(
            select(WalletPass).where(
                WalletPass.id == pass_id, WalletPass.org_id == org_id
            )
        )
        if not wallet_pass:
            raise HTTPException(status_code=404, detail="Wallet pass not found")
        wallet_pass.revoked = True
        await db.commit()
        await db.refresh(wallet_pass)
        return _pass_out(wallet_pass)
    except HTTPException:
        raise
    except Exception as e:
        log.error("revoke_wallet_pass failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
