"""Referral Tracking router — Sprint 9: Loyalty & Rewards.

Endpoint map
------------
    GET  /api/referrals                     — list referrals
    POST /api/referrals                     — create referral entry
    POST /api/referrals/{id}/qualify        — mark as qualified
    POST /api/referrals/{id}/reward         — mark as rewarded with points
"""
from __future__ import annotations

import logging
import secrets
import uuid
import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.referral_tracking import ReferralTracking

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/loyalty-referrals", tags=["loyalty-referrals"])


class ReferralIn(BaseModel):
    referrer_customer_id: uuid.UUID
    referred_customer_id: uuid.UUID | None = None


class RewardIn(BaseModel):
    reward_points: int


class ReferralOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    referrer_customer_id: uuid.UUID
    referred_customer_id: uuid.UUID | None
    referral_code: str
    status: str
    reward_points: int | None
    qualified_at: datetime.datetime | None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[ReferralOut])
async def list_referrals(
    referrer_customer_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None),
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(ReferralTracking).where(ReferralTracking.org_id == org_id)
        if referrer_customer_id is not None:
            q = q.where(ReferralTracking.referrer_customer_id == referrer_customer_id)
        if status is not None:
            q = q.where(ReferralTracking.status == status)
        q = q.order_by(ReferralTracking.created_at.desc())
        result = await db.execute(q)
        return [ReferralOut.model_validate(r) for r in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_referrals failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=ReferralOut, status_code=201)
async def create_referral(
    body: ReferralIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        referral_code = secrets.token_hex(5).upper()
        row = ReferralTracking(
            org_id=org_id,
            referrer_customer_id=body.referrer_customer_id,
            referred_customer_id=body.referred_customer_id,
            referral_code=referral_code,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return ReferralOut.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_referral failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


async def _get_referral(referral_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession) -> ReferralTracking:
    result = await db.execute(
        select(ReferralTracking).where(
            ReferralTracking.id == referral_id,
            ReferralTracking.org_id == org_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Referral not found")
    return row


@router.post("/{referral_id}/qualify", response_model=ReferralOut)
async def qualify_referral(
    referral_id: uuid.UUID,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        row = await _get_referral(referral_id, org_id, db)
        row.status = "qualified"
        row.qualified_at = datetime.datetime.utcnow()
        await db.commit()
        await db.refresh(row)
        return ReferralOut.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"qualify_referral failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{referral_id}/reward", response_model=ReferralOut)
async def reward_referral(
    referral_id: uuid.UUID,
    body: RewardIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        row = await _get_referral(referral_id, org_id, db)
        row.status = "rewarded"
        row.reward_points = body.reward_points
        await db.commit()
        await db.refresh(row)
        return ReferralOut.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"reward_referral failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")
