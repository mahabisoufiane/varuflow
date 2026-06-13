"""Referral program router (Item 68).

Endpoints under ``/api/referrals``:

    POST /codes                       mint or fetch the customer's code
    GET  /codes/{customer_id}         look up the code
    POST /claims                      open a referral for a referee
    POST /{referral_id}/qualify       PENDING → QUALIFIED
    POST /{referral_id}/reward        QUALIFIED → REWARDED
    POST /{referral_id}/reject        PENDING/QUALIFIED → REJECTED
    GET  ""                           list referrals (filter by status
                                      or referrer)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.invoicing import Customer
from app.models.referral import Referral, ReferralCode, ReferralStatus
from app.services import referral as svc
from app.services.audit import log_action

router = APIRouter(prefix="/api/referrals", tags=["referrals"])

log = logging.getLogger(__name__)


class CodeBody(BaseModel):
    customer_id: uuid.UUID


class CodeOut(BaseModel):
    customer_id: uuid.UUID
    code:        str
    created_at:  datetime


class ClaimBody(BaseModel):
    code:                 str
    referee_customer_id:  uuid.UUID


class RewardBody(BaseModel):
    amount: Decimal


class ReferralOut(BaseModel):
    id:                   uuid.UUID
    referrer_customer_id: uuid.UUID
    referee_customer_id:  uuid.UUID
    code:                 str
    status:               ReferralStatus
    reward_amount:        Decimal
    qualified_at:         datetime | None
    rewarded_at:          datetime | None
    rejected_at:          datetime | None
    created_at:           datetime


async def _assert_customer(db: AsyncSession, *, cid: uuid.UUID, org_id: uuid.UUID):
    row = await db.scalar(
        select(Customer).where(Customer.id == cid, Customer.org_id == org_id)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Customer not found")


async def _load(
    db: AsyncSession, *, referral_id: uuid.UUID, org_id: uuid.UUID
) -> Referral:
    row = await db.get(Referral, referral_id)
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Referral not found")
    return row


@router.post("/codes", response_model=CodeOut, status_code=status.HTTP_201_CREATED)
async def mint_code(
    body: CodeBody,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    await _assert_customer(db, cid=body.customer_id, org_id=member.org_id)

    # Idempotent: return the existing code if one is already minted.
    existing = await db.scalar(
        select(ReferralCode).where(
            ReferralCode.org_id == member.org_id,
            ReferralCode.customer_id == body.customer_id,
        )
    )
    if existing is not None:
        return existing

    org_codes = set(
        (
            await db.scalars(
                select(ReferralCode.code).where(
                    ReferralCode.org_id == member.org_id
                )
            )
        ).all()
    )
    code = svc.generate_code(org_codes)
    row = ReferralCode(
        org_id=member.org_id,
        customer_id=body.customer_id,
        code=code,
    )
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="referral.code_minted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="referral_code",
        target_id=str(row.id),
        request=request,
        extra={"customer_id": str(body.customer_id)},
    )
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/codes/{customer_id}", response_model=CodeOut)
async def get_code(
    customer_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _user, member = ctx
    row = await db.scalar(
        select(ReferralCode).where(
            ReferralCode.org_id == member.org_id,
            ReferralCode.customer_id == customer_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Code not found")
    return row


@router.post("/claims", response_model=ReferralOut, status_code=status.HTTP_201_CREATED)
async def open_claim(
    body: ClaimBody,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    try:
        code = svc.normalise_code(body.code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    code_row = await db.scalar(
        select(ReferralCode).where(
            ReferralCode.org_id == member.org_id,
            ReferralCode.code == code,
        )
    )
    if code_row is None:
        raise HTTPException(status_code=404, detail="Code not found")

    await _assert_customer(
        db, cid=body.referee_customer_id, org_id=member.org_id
    )

    existing_referees = (
        await db.scalars(
            select(Referral.referee_customer_id).where(
                Referral.org_id == member.org_id
            )
        )
    ).all()
    try:
        svc.validate_claim(
            referrer_id=str(code_row.customer_id),
            referee_id=str(body.referee_customer_id),
            existing_referees=[str(x) for x in existing_referees],
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    row = Referral(
        org_id=member.org_id,
        referrer_customer_id=code_row.customer_id,
        referee_customer_id=body.referee_customer_id,
        code=code,
        status=ReferralStatus.PENDING,
    )
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="referral.claim_opened",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="referral",
        target_id=str(row.id),
        request=request,
        extra={"code": code},
    )
    await db.commit()
    await db.refresh(row)
    return row


@router.post("/{referral_id}/qualify", response_model=ReferralOut)
async def qualify(
    referral_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, referral_id=referral_id, org_id=member.org_id)
    try:
        svc.assert_transition(row.status.value, "QUALIFIED")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    now = datetime.now(timezone.utc)
    row.status = ReferralStatus.QUALIFIED
    row.qualified_at = now
    await log_action(
        db,
        action="referral.qualified",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="referral",
        target_id=str(row.id),
        request=request,
        extra={},
    )
    await db.commit()
    await db.refresh(row)
    return row


@router.post("/{referral_id}/reward", response_model=ReferralOut)
async def reward(
    referral_id: uuid.UUID,
    body: RewardBody,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, referral_id=referral_id, org_id=member.org_id)
    try:
        svc.assert_transition(row.status.value, "REWARDED")
        amount = svc.validate_reward_amount(body.amount)
    except ValueError as e:
        raise HTTPException(
            status_code=409 if "transition" in str(e) else 400, detail=str(e)
        )
    now = datetime.now(timezone.utc)
    row.status = ReferralStatus.REWARDED
    row.reward_amount = amount
    row.rewarded_at = now
    await log_action(
        db,
        action="referral.rewarded",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="referral",
        target_id=str(row.id),
        request=request,
        extra={"amount": str(amount)},
    )
    await db.commit()
    await db.refresh(row)
    return row


@router.post("/{referral_id}/reject", response_model=ReferralOut)
async def reject(
    referral_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, referral_id=referral_id, org_id=member.org_id)
    try:
        svc.assert_transition(row.status.value, "REJECTED")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    now = datetime.now(timezone.utc)
    row.status = ReferralStatus.REJECTED
    row.rejected_at = now
    await log_action(
        db,
        action="referral.rejected",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="referral",
        target_id=str(row.id),
        request=request,
        extra={},
    )
    await db.commit()
    await db.refresh(row)
    return row


@router.get("", response_model=list[ReferralOut])
async def list_referrals(
    referrer_customer_id: uuid.UUID | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _user, member = ctx
    stmt = select(Referral).where(Referral.org_id == member.org_id)
    if referrer_customer_id is not None:
        stmt = stmt.where(
            Referral.referrer_customer_id == referrer_customer_id
        )
    if status_ is not None:
        if status_ not in svc.ALLOWED_STATUSES:
            raise HTTPException(status_code=400, detail="invalid status")
        stmt = stmt.where(Referral.status == ReferralStatus(status_))
    rows = (
        await db.scalars(stmt.order_by(Referral.created_at.desc()))
    ).all()
    return list(rows)
