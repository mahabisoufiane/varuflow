"""Gift cards & service bundles router (v49 — Item 33).

Endpoint map
------------
Gift cards
    POST   /api/gift-cards/issue         — issue a new card
    GET    /api/gift-cards               — list (org-scoped, admin)
    GET    /api/gift-cards/by-code/{code}/balance — public-ish balance check
    POST   /api/gift-cards/redeem        — redeem against an amount
    POST   /api/gift-cards/{id}/void     — void (soft-kill)
Bundles
    POST   /api/gift-cards/bundles                — create a bundle
    GET    /api/gift-cards/bundles                — list bundles
    DELETE /api/gift-cards/bundles/{id}           — deactivate
    POST   /api/gift-cards/bundles/{id}/purchase  — sell to a customer
    GET    /api/gift-cards/bundles/customer/{cid} — list customer ledger

The balance-check endpoint is intentionally lightweight: it still
requires an authenticated org member (so we don't expose a gift-
card enumeration oracle to anonymous callers) but returns only the
minimum fields a cashier needs at the till.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.gift_cards import BundleRedemption, GiftCard, ServiceBundle
from app.services.audit import log_action
from app.services.gift_card_service import (
    compute_remaining_sessions,
    expiry_from_days,
    is_expired,
    issue_gift_card,
    redeem_gift_card,
)

router = APIRouter(prefix="/api/gift-cards", tags=["gift-cards"])


def _org(ctx: tuple) -> uuid.UUID:
    _user, member = ctx
    return member.org_id


# ── Schemas ───────────────────────────────────────────────────────


class GiftCardIssueIn(BaseModel):
    initial_value: Decimal = Field(..., gt=Decimal("0"), le=Decimal("1000000"))
    customer_id: Optional[uuid.UUID] = None
    valid_days: Optional[int] = Field(default=365, ge=0, le=3650)


class GiftCardOut(BaseModel):
    id: uuid.UUID
    code: str
    initial_value: Decimal
    remaining_value: Decimal
    issued_to_customer_id: Optional[uuid.UUID]
    expires_at: Optional[datetime]
    status: str

    model_config = ConfigDict(from_attributes=True)


class GiftCardBalanceOut(BaseModel):
    code: str
    remaining_value: Decimal
    status: str
    expires_at: Optional[datetime]
    is_expired: bool


class GiftCardRedeemIn(BaseModel):
    code: str = Field(..., min_length=4, max_length=32)
    amount: Decimal = Field(..., gt=Decimal("0"), le=Decimal("1000000"))


class GiftCardRedeemOut(BaseModel):
    code: str
    applied: Decimal
    remaining_balance: Decimal
    shortfall: Decimal


class BundleCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    price: Decimal = Field(..., ge=Decimal("0"), le=Decimal("1000000"))
    valid_days: int = Field(default=365, ge=0, le=3650)
    services: list[uuid.UUID] = Field(default_factory=list)
    sessions_total: int = Field(..., ge=1, le=1000)


class BundleOut(BaseModel):
    id: uuid.UUID
    name: str
    price: Decimal
    valid_days: int
    services: list[str]
    sessions_total: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class BundlePurchaseIn(BaseModel):
    customer_id: uuid.UUID


class CustomerBundleOut(BaseModel):
    bundle_id: uuid.UUID
    bundle_name: str
    sessions_remaining: int
    expires_at: Optional[datetime]


# ── Gift card endpoints ───────────────────────────────────────────


@router.post("/issue", response_model=GiftCardOut, status_code=status.HTTP_201_CREATED)
async def issue_card(
    body: GiftCardIssueIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    expires_at = expiry_from_days(body.valid_days) if body.valid_days else None
    card = await issue_gift_card(
        db,
        org_id=member.org_id,
        initial_value=body.initial_value,
        expires_at=expires_at,
        issued_to_customer_id=body.customer_id,
    )
    if card is None:
        raise HTTPException(status_code=500, detail="gift_card_issue_failed")
    await log_action(
        db,
        action="gift_card.issued",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="gift_card",
        target_id=str(card.id),
        request=request,
        extra={
            "code": card.code,
            "initial_value": str(card.initial_value),
            "customer_id": str(body.customer_id) if body.customer_id else None,
        },
    )
    await db.commit()
    return card


@router.get("", response_model=list[GiftCardOut])
async def list_cards(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(GiftCard)
            .where(GiftCard.org_id == _org(ctx))
            .order_by(GiftCard.created_at.desc())
            .limit(500)
        )
    ).scalars().all()
    return rows


@router.get("/by-code/{code}/balance", response_model=GiftCardBalanceOut)
async def check_balance(
    code: str,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Cashier-facing balance lookup — org-scoped, no PII returned."""
    card = (
        await db.execute(
            select(GiftCard).where(
                and_(GiftCard.org_id == _org(ctx), GiftCard.code == code.strip().upper())
            )
        )
    ).scalar_one_or_none()
    if card is None:
        raise HTTPException(status_code=404, detail="gift_card_not_found")
    return GiftCardBalanceOut(
        code=card.code,
        remaining_value=card.remaining_value,
        status=card.status,
        expires_at=card.expires_at,
        is_expired=is_expired(card),
    )


@router.post("/redeem", response_model=GiftCardRedeemOut)
async def redeem_card(
    body: GiftCardRedeemIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    result = await redeem_gift_card(
        db, org_id=member.org_id, code=body.code, amount_due=body.amount
    )
    if result is None:
        raise HTTPException(status_code=404, detail="gift_card_not_found")
    await log_action(
        db,
        action="gift_card.redeemed",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="gift_card",
        target_id=body.code,
        request=request,
        extra={
            "amount_due": str(body.amount),
            "applied": str(result.applied),
            "remaining": str(result.remaining_balance),
        },
    )
    await db.commit()
    return GiftCardRedeemOut(
        code=body.code.strip().upper(),
        applied=result.applied,
        remaining_balance=result.remaining_balance,
        shortfall=result.shortfall,
    )


@router.post("/{card_id}/void", response_model=GiftCardOut)
async def void_card(
    card_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    card = (
        await db.execute(
            select(GiftCard).where(
                and_(GiftCard.id == card_id, GiftCard.org_id == member.org_id)
            )
        )
    ).scalar_one_or_none()
    if card is None:
        raise HTTPException(status_code=404, detail="gift_card_not_found")
    card.status = "void"
    await log_action(
        db,
        action="gift_card.voided",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="gift_card",
        target_id=str(card.id),
        request=request,
    )
    await db.commit()
    return card


# ── Bundle endpoints ──────────────────────────────────────────────


@router.post("/bundles", response_model=BundleOut, status_code=status.HTTP_201_CREATED)
async def create_bundle(
    body: BundleCreateIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    bundle = ServiceBundle(
        id=uuid.uuid4(),
        org_id=member.org_id,
        name=body.name,
        price=body.price,
        valid_days=body.valid_days,
        services=[str(s) for s in body.services],
        sessions_total=body.sessions_total,
        is_active=True,
    )
    db.add(bundle)
    await db.flush()
    await log_action(
        db,
        action="bundle.created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="service_bundle",
        target_id=str(bundle.id),
        request=request,
        extra={"name": body.name, "sessions_total": body.sessions_total},
    )
    await db.commit()
    return bundle


@router.get("/bundles", response_model=list[BundleOut])
async def list_bundles(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(ServiceBundle)
            .where(ServiceBundle.org_id == _org(ctx))
            .order_by(ServiceBundle.created_at.desc())
        )
    ).scalars().all()
    return rows


@router.delete("/bundles/{bundle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_bundle(
    bundle_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    bundle = (
        await db.execute(
            select(ServiceBundle).where(
                and_(ServiceBundle.id == bundle_id, ServiceBundle.org_id == member.org_id)
            )
        )
    ).scalar_one_or_none()
    if bundle is None:
        raise HTTPException(status_code=404, detail="bundle_not_found")
    bundle.is_active = False
    await log_action(
        db,
        action="bundle.deactivated",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="service_bundle",
        target_id=str(bundle.id),
        request=request,
    )
    await db.commit()


@router.post("/bundles/{bundle_id}/purchase", status_code=status.HTTP_201_CREATED)
async def purchase_bundle(
    bundle_id: uuid.UUID,
    body: BundlePurchaseIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    bundle = (
        await db.execute(
            select(ServiceBundle).where(
                and_(ServiceBundle.id == bundle_id, ServiceBundle.org_id == member.org_id)
            )
        )
    ).scalar_one_or_none()
    if bundle is None or not bundle.is_active:
        raise HTTPException(status_code=404, detail="bundle_not_found")
    expires_at = expiry_from_days(bundle.valid_days)
    row = BundleRedemption(
        id=uuid.uuid4(),
        org_id=member.org_id,
        bundle_id=bundle.id,
        customer_id=body.customer_id,
        appointment_id=None,
        kind="purchase",
        expires_at=expires_at,
    )
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="bundle.purchased",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="bundle_redemption",
        target_id=str(row.id),
        request=request,
        extra={"bundle_id": str(bundle.id), "customer_id": str(body.customer_id)},
    )
    await db.commit()
    return {"id": str(row.id), "expires_at": expires_at}


@router.get("/bundles/customer/{customer_id}", response_model=list[CustomerBundleOut])
async def list_customer_bundles(
    customer_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(BundleRedemption).where(
                and_(
                    BundleRedemption.org_id == _org(ctx),
                    BundleRedemption.customer_id == customer_id,
                )
            )
        )
    ).scalars().all()
    per_bundle: dict = {}
    for row in rows:
        per_bundle.setdefault(row.bundle_id, {"purchases": [], "uses": 0})
        if row.kind == "purchase":
            per_bundle[row.bundle_id]["purchases"].append(row)
        else:
            per_bundle[row.bundle_id]["uses"] += 1
    out: list[CustomerBundleOut] = []
    for bundle_id, agg in per_bundle.items():
        if not agg["purchases"]:
            continue
        bundle = await db.get(ServiceBundle, bundle_id)
        if bundle is None:
            continue
        remaining = compute_remaining_sessions(
            purchases=len(agg["purchases"]),
            uses=agg["uses"],
            sessions_per_purchase=bundle.sessions_total,
        )
        earliest = min(
            (p.expires_at for p in agg["purchases"] if p.expires_at is not None),
            default=None,
        )
        out.append(
            CustomerBundleOut(
                bundle_id=bundle.id,
                bundle_name=bundle.name,
                sessions_remaining=remaining,
                expires_at=earliest,
            )
        )
    return out
