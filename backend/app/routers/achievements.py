"""Achievements router — Sprint 9: Loyalty & Rewards.

Endpoint map
------------
    GET  /api/achievements                  — list achievement definitions
    POST /api/achievements                  — create achievement
    PATCH /api/achievements/{id}            — update achievement
    DELETE /api/achievements/{id}           — delete achievement
    GET  /api/achievements/earned           — earned achievements for a customer
    POST /api/achievements/award            — award achievement to customer
"""
from __future__ import annotations

import logging
import uuid
import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.achievement import Achievement, CustomerAchievement
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/achievements", tags=["achievements"], dependencies=[Depends(require_module("hr"))])


# ── Schemas ────────────────────────────────────────────────────────

class AchievementIn(BaseModel):
    title: str
    description: str | None = None
    badge_icon: str | None = None
    badge_color: str = "#FFD700"
    trigger_type: str
    trigger_value: int | None = None


class AchievementPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    badge_icon: str | None = None
    badge_color: str | None = None
    trigger_type: str | None = None
    trigger_value: int | None = None


class AchievementOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    title: str
    description: str | None
    badge_icon: str | None
    badge_color: str
    trigger_type: str
    trigger_value: int | None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class AwardIn(BaseModel):
    customer_id: uuid.UUID
    achievement_id: uuid.UUID


class CustomerAchievementOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    achievement_id: uuid.UUID
    awarded_at: datetime.datetime
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# ── Endpoints ──────────────────────────────────────────────────────

@router.get("", response_model=list[AchievementOut])
async def list_achievements(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        result = await db.execute(
            select(Achievement)
            .where(Achievement.org_id == org_id)
            .order_by(Achievement.created_at)
        )
        return [AchievementOut.model_validate(r) for r in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_achievements failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=AchievementOut, status_code=201)
async def create_achievement(
    body: AchievementIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        row = Achievement(
            org_id=org_id,
            title=body.title,
            description=body.description,
            badge_icon=body.badge_icon,
            badge_color=body.badge_color,
            trigger_type=body.trigger_type,
            trigger_value=body.trigger_value,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return AchievementOut.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_achievement failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{achievement_id}", response_model=AchievementOut)
async def update_achievement(
    achievement_id: uuid.UUID,
    body: AchievementPatch,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        result = await db.execute(
            select(Achievement).where(
                Achievement.id == achievement_id,
                Achievement.org_id == org_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Achievement not found")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        await db.commit()
        await db.refresh(row)
        return AchievementOut.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_achievement failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{achievement_id}", status_code=204)
async def delete_achievement(
    achievement_id: uuid.UUID,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        result = await db.execute(
            select(Achievement).where(
                Achievement.id == achievement_id,
                Achievement.org_id == org_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Achievement not found")
        await db.delete(row)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_achievement failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/earned", response_model=list[CustomerAchievementOut])
async def list_earned_achievements(
    customer_id: uuid.UUID = Query(...),
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        result = await db.execute(
            select(CustomerAchievement).where(
                CustomerAchievement.org_id == org_id,
                CustomerAchievement.customer_id == customer_id,
            ).order_by(CustomerAchievement.awarded_at.desc())
        )
        return [CustomerAchievementOut.model_validate(r) for r in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_earned_achievements failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/award", response_model=CustomerAchievementOut, status_code=201)
async def award_achievement(
    body: AwardIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        # Verify achievement belongs to org
        ach_result = await db.execute(
            select(Achievement).where(
                Achievement.id == body.achievement_id,
                Achievement.org_id == org_id,
            )
        )
        if ach_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Achievement not found")
        row = CustomerAchievement(
            org_id=org_id,
            customer_id=body.customer_id,
            achievement_id=body.achievement_id,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return CustomerAchievementOut.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"award_achievement failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")
