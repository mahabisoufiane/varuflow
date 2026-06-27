"""Loyalty Streaks router — Sprint 9: Loyalty & Rewards.

Endpoint map
------------
    GET /api/streaks                                    — list streaks for customer
    PUT /api/streaks/{customer_id}/{streak_type}        — upsert streak
    GET /api/streaks/leaderboard                        — top 10 by current_count
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
from app.middleware.plan_check import require_module
from .loyalty_streak import LoyaltyStreak

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/streaks", tags=["loyalty-streaks"], dependencies=[Depends(require_module("crm"))])


class StreakUpsertIn(BaseModel):
    current_count: int
    longest_count: int
    last_activity_date: datetime.date | None = None
    streak_start_date: datetime.date | None = None
    milestone_rewards: dict | None = None


class StreakOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    streak_type: str
    current_count: int
    longest_count: int
    last_activity_date: datetime.date | None
    streak_start_date: datetime.date | None
    milestone_rewards: dict | None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class LeaderboardEntry(BaseModel):
    customer_id: uuid.UUID
    streak_type: str
    current_count: int
    longest_count: int
    last_activity_date: datetime.date | None

    model_config = ConfigDict(from_attributes=True)


@router.get("/leaderboard", response_model=list[LeaderboardEntry])
async def streak_leaderboard(
    streak_type: str = Query("monthly_visit"),
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        result = await db.execute(
            select(LoyaltyStreak).where(
                LoyaltyStreak.org_id == org_id,
                LoyaltyStreak.streak_type == streak_type,
            ).order_by(LoyaltyStreak.current_count.desc()).limit(10)
        )
        return [LeaderboardEntry.model_validate(r) for r in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"streak_leaderboard failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=list[StreakOut])
async def list_streaks(
    customer_id: uuid.UUID = Query(...),
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        result = await db.execute(
            select(LoyaltyStreak).where(
                LoyaltyStreak.org_id == org_id,
                LoyaltyStreak.customer_id == customer_id,
            ).order_by(LoyaltyStreak.streak_type)
        )
        return [StreakOut.model_validate(r) for r in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_streaks failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{customer_id}/{streak_type}", response_model=StreakOut)
async def upsert_streak(
    customer_id: uuid.UUID,
    streak_type: str,
    body: StreakUpsertIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        now = datetime.datetime.now(datetime.timezone.utc)
        stmt = (
            pg_insert(LoyaltyStreak)
            .values(
                org_id=org_id,
                customer_id=customer_id,
                streak_type=streak_type,
                current_count=body.current_count,
                longest_count=body.longest_count,
                last_activity_date=body.last_activity_date,
                streak_start_date=body.streak_start_date,
                milestone_rewards=body.milestone_rewards,
                updated_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_loyalty_streaks_org_customer_type",
                set_={
                    "current_count": body.current_count,
                    "longest_count": body.longest_count,
                    "last_activity_date": body.last_activity_date,
                    "streak_start_date": body.streak_start_date,
                    "milestone_rewards": body.milestone_rewards,
                    "updated_at": now,
                },
            )
            .returning(LoyaltyStreak)
        )
        result = await db.execute(stmt)
        await db.commit()
        row = result.scalar_one()
        return StreakOut.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"upsert_streak failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")
