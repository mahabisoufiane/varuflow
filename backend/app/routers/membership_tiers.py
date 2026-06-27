"""Membership Tiers router — Sprint 9: Loyalty & Rewards.

Endpoint map
------------
    GET  /api/membership-tiers                              — list tiers
    POST /api/membership-tiers                              — create tier
    PATCH /api/membership-tiers/{id}                        — update tier
    DELETE /api/membership-tiers/{id}                       — delete tier
    GET  /api/membership-tiers/memberships                  — get customer membership
    PUT  /api/membership-tiers/memberships/{customer_id}    — assign/update tier
"""
from __future__ import annotations

import logging
import uuid
import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.membership_tier import CustomerMembership, MembershipTier

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/membership-tiers", tags=["membership-tiers"])


# ── Schemas ────────────────────────────────────────────────────────

class TierIn(BaseModel):
    name: str
    min_points: int = 0
    card_color: str = "#CD7F32"
    card_text_color: str = "#FFFFFF"
    benefits: str | None = None
    sort_order: int = 0


class TierPatch(BaseModel):
    name: str | None = None
    min_points: int | None = None
    card_color: str | None = None
    card_text_color: str | None = None
    benefits: str | None = None
    sort_order: int | None = None


class TierOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    min_points: int
    card_color: str
    card_text_color: str
    benefits: str | None
    sort_order: int
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class MembershipIn(BaseModel):
    tier_id: uuid.UUID | None = None
    valid_until: datetime.datetime | None = None


class MembershipOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    tier_id: uuid.UUID | None
    awarded_at: datetime.datetime
    valid_until: datetime.datetime | None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# ── Tier endpoints ─────────────────────────────────────────────────

@router.get("", response_model=list[TierOut])
async def list_tiers(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        result = await db.execute(
            select(MembershipTier)
            .where(MembershipTier.org_id == org_id)
            .order_by(MembershipTier.sort_order)
        )
        return [TierOut.model_validate(r) for r in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_tiers failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=TierOut, status_code=201)
async def create_tier(
    body: TierIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        row = MembershipTier(
            org_id=org_id,
            name=body.name,
            min_points=body.min_points,
            card_color=body.card_color,
            card_text_color=body.card_text_color,
            benefits=body.benefits,
            sort_order=body.sort_order,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return TierOut.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_tier failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{tier_id}", response_model=TierOut)
async def update_tier(
    tier_id: uuid.UUID,
    body: TierPatch,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        result = await db.execute(
            select(MembershipTier).where(
                MembershipTier.id == tier_id,
                MembershipTier.org_id == org_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Membership tier not found")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        await db.commit()
        await db.refresh(row)
        return TierOut.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_tier failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{tier_id}", status_code=204)
async def delete_tier(
    tier_id: uuid.UUID,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        result = await db.execute(
            select(MembershipTier).where(
                MembershipTier.id == tier_id,
                MembershipTier.org_id == org_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Membership tier not found")
        await db.delete(row)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_tier failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Membership endpoints ───────────────────────────────────────────

@router.get("/memberships", response_model=MembershipOut | dict)
async def get_customer_membership(
    customer_id: uuid.UUID = Query(...),
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        result = await db.execute(
            select(CustomerMembership).where(
                CustomerMembership.org_id == org_id,
                CustomerMembership.customer_id == customer_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return {}
        return MembershipOut.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_customer_membership failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/memberships/{customer_id}", response_model=MembershipOut)
async def upsert_customer_membership(
    customer_id: uuid.UUID,
    body: MembershipIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        now = datetime.datetime.utcnow()
        stmt = (
            pg_insert(CustomerMembership)
            .values(
                org_id=org_id,
                customer_id=customer_id,
                tier_id=body.tier_id,
                awarded_at=now,
                valid_until=body.valid_until,
            )
            .on_conflict_do_update(
                constraint="uq_customer_memberships_org_customer",
                set_={
                    "tier_id": body.tier_id,
                    "awarded_at": now,
                    "valid_until": body.valid_until,
                },
            )
            .returning(CustomerMembership)
        )
        result = await db.execute(stmt)
        await db.commit()
        row = result.scalar_one()
        return MembershipOut.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"upsert_customer_membership failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")
