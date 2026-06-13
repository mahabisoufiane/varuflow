"""Customer Preferences router — Sprint 9: Personalization.

Endpoint map
------------
    GET /api/preferences/{customer_id}  — get preferences (or empty dict)
    PUT /api/preferences/{customer_id}  — upsert preferences
"""
from __future__ import annotations

import logging
import uuid
import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.customer_preferences import CustomerPreference

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/preferences", tags=["customer-preferences"])


class PreferenceIn(BaseModel):
    favorite_staff_user_id: uuid.UUID | None = None
    preferred_time_of_day: str | None = None
    preferred_day_of_week: int | None = None
    allergies: str | None = None
    communication_channel: str = "push"
    notes: str | None = None


class PreferenceOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    favorite_staff_user_id: uuid.UUID | None
    preferred_time_of_day: str | None
    preferred_day_of_week: int | None
    allergies: str | None
    communication_channel: str
    notes: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("/{customer_id}", response_model=PreferenceOut | dict)
async def get_preferences(
    customer_id: uuid.UUID,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        result = await db.execute(
            select(CustomerPreference).where(
                CustomerPreference.org_id == org_id,
                CustomerPreference.customer_id == customer_id,
            )
        )
        pref = result.scalar_one_or_none()
        if pref is None:
            return {}
        return PreferenceOut.model_validate(pref)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_preferences failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{customer_id}", response_model=PreferenceOut)
async def upsert_preferences(
    customer_id: uuid.UUID,
    body: PreferenceIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        now = datetime.datetime.utcnow()
        stmt = (
            pg_insert(CustomerPreference)
            .values(
                org_id=org_id,
                customer_id=customer_id,
                favorite_staff_user_id=body.favorite_staff_user_id,
                preferred_time_of_day=body.preferred_time_of_day,
                preferred_day_of_week=body.preferred_day_of_week,
                allergies=body.allergies,
                communication_channel=body.communication_channel,
                notes=body.notes,
                updated_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_customer_preferences_org_customer",
                set_={
                    "favorite_staff_user_id": body.favorite_staff_user_id,
                    "preferred_time_of_day": body.preferred_time_of_day,
                    "preferred_day_of_week": body.preferred_day_of_week,
                    "allergies": body.allergies,
                    "communication_channel": body.communication_channel,
                    "notes": body.notes,
                    "updated_at": now,
                },
            )
            .returning(CustomerPreference)
        )
        result = await db.execute(stmt)
        await db.commit()
        row = result.scalar_one()
        return PreferenceOut.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"upsert_preferences failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")
