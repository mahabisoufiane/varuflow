"""Loyalty program router (Item 35).

Endpoint map
------------
    GET  /api/loyalty/program                   — active program config
    PUT  /api/loyalty/program                   — upsert program config
    GET  /api/loyalty/accounts/{customer_id}    — customer card (balance + tier + history head)
    GET  /api/loyalty/accounts/{customer_id}/transactions
                                                — ledger (paginated)
    POST /api/loyalty/accounts/{customer_id}/adjust
                                                — staff manual grant/revoke
    POST /api/loyalty/accounts/{customer_id}/redeem
                                                — redeem points as discount
    GET  /api/loyalty/export/{customer_id}      — CSV export of one customer's ledger
    GET  /api/loyalty/tiers                     — tier thresholds (for UI)
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.features.invoicing.models import Customer
from .models import LoyaltyAccount, LoyaltyProgram, LoyaltyTransaction
from app.services.audit import log_action
from app.services.loyalty_engine import (
    TIER_THRESHOLDS,
    active_program,
    adjust_points,
    ensure_account,
    redeem_points,
)

router = APIRouter(prefix="/api/loyalty", tags=["loyalty"], dependencies=[Depends(require_module("crm"))])


# ── Schemas ───────────────────────────────────────────────────────


class ProgramOut(BaseModel):
    id: uuid.UUID | None = None
    name: str = "Loyalty"
    points_per_currency_unit: Decimal = Decimal("1")
    redemption_rate: Decimal = Decimal("0.01")
    expiry_days: int = 365
    is_active: bool = True


class ProgramIn(BaseModel):
    name: str = Field("Loyalty", min_length=1, max_length=120)
    points_per_currency_unit: Decimal = Field(Decimal("1"), ge=Decimal("0"))
    redemption_rate: Decimal = Field(Decimal("0.01"), ge=Decimal("0"))
    expiry_days: int = Field(365, ge=0, le=3650)
    is_active: bool = True

    @field_validator("points_per_currency_unit", "redemption_rate", mode="before")
    @classmethod
    def _to_decimal(cls, v):
        return v if isinstance(v, Decimal) else Decimal(str(v))


class AccountOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    points_balance: int
    lifetime_points: int
    tier: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionOut(BaseModel):
    id: uuid.UUID
    points: int
    type: str
    source_type: str | None = None
    source_id: str | None = None
    reason: str | None = None
    expires_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdjustIn(BaseModel):
    delta: int
    reason: str = Field(..., min_length=1, max_length=500)


class RedeemIn(BaseModel):
    points: int = Field(..., gt=0)
    source_type: str = Field(..., min_length=1, max_length=32)
    source_id: str = Field(..., min_length=1, max_length=128)
    cap: Decimal | None = Field(default=None, ge=Decimal("0"))


class RedeemOut(BaseModel):
    transaction_id: uuid.UUID
    points: int
    discount: Decimal
    new_balance: int


# ── Helpers ───────────────────────────────────────────────────────


async def _get_customer_in_org(
    db: AsyncSession, *, org_id: uuid.UUID, customer_id: uuid.UUID
) -> Customer:
    cust = await db.get(Customer, customer_id)
    if cust is None or cust.org_id != org_id:
        raise HTTPException(status_code=404, detail="customer_not_found")
    return cust


def _program_to_out(p: LoyaltyProgram | None) -> ProgramOut:
    if p is None:
        return ProgramOut()
    return ProgramOut(
        id=p.id,
        name=p.name,
        points_per_currency_unit=p.points_per_currency_unit,
        redemption_rate=p.redemption_rate,
        expiry_days=p.expiry_days,
        is_active=p.is_active,
    )


# ── Program configuration ────────────────────────────────────────


@router.get("/program", response_model=ProgramOut)
async def get_program(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _user, member = ctx
    prog = await active_program(db, member.org_id)
    return _program_to_out(prog)


@router.put("/program", response_model=ProgramOut)
async def set_program(
    body: ProgramIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    # Deactivate any prior active programs so "one active per org".
    existing = await active_program(db, member.org_id)
    if existing is not None:
        existing.is_active = False

    prog = LoyaltyProgram(
        id=uuid.uuid4(),
        org_id=member.org_id,
        name=body.name,
        points_per_currency_unit=body.points_per_currency_unit,
        redemption_rate=body.redemption_rate,
        expiry_days=body.expiry_days,
        is_active=body.is_active,
    )
    db.add(prog)
    await log_action(
        db,
        action="loyalty.program_updated",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="loyalty_program",
        target_id=str(prog.id),
        request=request,
        extra={
            "points_per_unit": str(prog.points_per_currency_unit),
            "redemption_rate": str(prog.redemption_rate),
            "expiry_days": prog.expiry_days,
            "is_active": prog.is_active,
        },
    )
    await db.commit()
    await db.refresh(prog)
    return _program_to_out(prog)


@router.get("/tiers")
async def get_tiers(ctx: tuple = Depends(get_current_member)):
    return [
        {"name": name, "threshold": threshold}
        for name, threshold in TIER_THRESHOLDS.items()
    ]


# ── Account views ─────────────────────────────────────────────────


@router.get("/accounts/{customer_id}", response_model=AccountOut)
async def get_account(
    customer_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _user, member = ctx
    await _get_customer_in_org(db, org_id=member.org_id, customer_id=customer_id)
    account = await ensure_account(db, org_id=member.org_id, customer_id=customer_id)
    await db.commit()
    return account


@router.get(
    "/accounts/{customer_id}/transactions",
    response_model=list[TransactionOut],
)
async def list_transactions(
    customer_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _user, member = ctx
    await _get_customer_in_org(db, org_id=member.org_id, customer_id=customer_id)
    # Get account without creating it (silent empty if none).
    acc_stmt = select(LoyaltyAccount).where(
        LoyaltyAccount.org_id == member.org_id,
        LoyaltyAccount.customer_id == customer_id,
    )
    account = (await db.execute(acc_stmt)).scalar_one_or_none()
    if account is None:
        return []
    stmt = (
        select(LoyaltyTransaction)
        .where(LoyaltyTransaction.account_id == account.id)
        .order_by(LoyaltyTransaction.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


@router.post("/accounts/{customer_id}/adjust", response_model=AccountOut)
async def adjust(
    customer_id: uuid.UUID,
    body: AdjustIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    await _get_customer_in_org(db, org_id=member.org_id, customer_id=customer_id)
    try:
        tx = await adjust_points(
            db,
            org_id=member.org_id,
            customer_id=customer_id,
            delta=int(body.delta),
            reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await log_action(
        db,
        action="loyalty.points_adjusted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="customer",
        target_id=str(customer_id),
        request=request,
        extra={"delta": int(body.delta), "reason": body.reason, "tx_id": str(tx.id)},
    )
    await db.commit()
    account = await ensure_account(db, org_id=member.org_id, customer_id=customer_id)
    return account


@router.post("/accounts/{customer_id}/redeem", response_model=RedeemOut)
async def redeem(
    customer_id: uuid.UUID,
    body: RedeemIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    await _get_customer_in_org(db, org_id=member.org_id, customer_id=customer_id)
    try:
        tx, discount = await redeem_points(
            db,
            org_id=member.org_id,
            customer_id=customer_id,
            points=int(body.points),
            source_type=body.source_type,
            source_id=body.source_id,
            cap=body.cap,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await log_action(
        db,
        action="loyalty.points_redeemed",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="customer",
        target_id=str(customer_id),
        request=request,
        extra={
            "points": int(body.points),
            "discount": str(discount),
            "source_type": body.source_type,
            "source_id": body.source_id,
            "tx_id": str(tx.id),
        },
    )
    await db.commit()
    account = await ensure_account(db, org_id=member.org_id, customer_id=customer_id)
    return RedeemOut(
        transaction_id=tx.id,
        points=int(body.points),
        discount=discount,
        new_balance=int(account.points_balance),
    )


# ── Export ────────────────────────────────────────────────────────


@router.get("/export/{customer_id}")
async def export_customer(
    customer_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return a CSV of the customer's full ledger. Same columns as the
    UI table so ops can diff against screenshots."""
    _user, member = ctx
    await _get_customer_in_org(db, org_id=member.org_id, customer_id=customer_id)
    acc_stmt = select(LoyaltyAccount).where(
        LoyaltyAccount.org_id == member.org_id,
        LoyaltyAccount.customer_id == customer_id,
    )
    account = (await db.execute(acc_stmt)).scalar_one_or_none()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "created_at",
        "type",
        "points",
        "source_type",
        "source_id",
        "reason",
        "expires_at",
    ])
    if account is not None:
        stmt = (
            select(LoyaltyTransaction)
            .where(LoyaltyTransaction.account_id == account.id)
            .order_by(LoyaltyTransaction.created_at.asc())
        )
        for row in (await db.execute(stmt)).scalars():
            writer.writerow([
                row.created_at.isoformat() if row.created_at else "",
                row.type,
                row.points,
                row.source_type or "",
                row.source_id or "",
                (row.reason or "").replace("\n", " "),
                row.expires_at.isoformat() if row.expires_at else "",
            ])

    data = buf.getvalue()
    return StreamingResponse(
        iter([data]),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="loyalty_{customer_id}.csv"'
            ),
        },
    )
