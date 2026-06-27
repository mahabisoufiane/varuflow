"""AI Recommendations router — Sprint 9: Personalization.

Endpoint map
------------
    GET    /api/recommendations                    — list with filters
    POST   /api/recommendations                    — create
    POST   /api/recommendations/{id}/shown         — mark shown
    POST   /api/recommendations/{id}/accept        — accept
    POST   /api/recommendations/{id}/reject        — reject
    DELETE /api/recommendations/{id}               — delete
"""
from __future__ import annotations

import logging
import uuid
import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.features.ai.ai_recommendation import AiRecommendation

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/recommendations", tags=["ai-recommendations"], dependencies=[Depends(require_module("ai"))])


class RecommendationIn(BaseModel):
    customer_id: uuid.UUID
    product_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    title: str
    reason: str | None = None
    score: float | None = None


class RecommendationOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    product_id: uuid.UUID | None
    service_id: uuid.UUID | None
    title: str
    reason: str | None
    score: float | None
    is_shown: bool
    is_accepted: bool | None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[RecommendationOut])
async def list_recommendations(
    customer_id: uuid.UUID | None = Query(None),
    is_shown: bool | None = Query(None),
    is_accepted: bool | None = Query(None),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(AiRecommendation).where(AiRecommendation.org_id == org_id)
        if customer_id is not None:
            q = q.where(AiRecommendation.customer_id == customer_id)
        if is_shown is not None:
            q = q.where(AiRecommendation.is_shown == is_shown)
        if is_accepted is not None:
            q = q.where(AiRecommendation.is_accepted == is_accepted)
        q = q.order_by(AiRecommendation.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(q)
        return [RecommendationOut.model_validate(r) for r in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_recommendations failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=RecommendationOut, status_code=201)
async def create_recommendation(
    body: RecommendationIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        rec = AiRecommendation(
            org_id=org_id,
            customer_id=body.customer_id,
            product_id=body.product_id,
            service_id=body.service_id,
            title=body.title,
            reason=body.reason,
            score=body.score,
        )
        db.add(rec)
        await db.commit()
        await db.refresh(rec)
        return RecommendationOut.model_validate(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_recommendation failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


async def _get_rec(rec_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession) -> AiRecommendation:
    result = await db.execute(
        select(AiRecommendation).where(
            AiRecommendation.id == rec_id,
            AiRecommendation.org_id == org_id,
        )
    )
    rec = result.scalar_one_or_none()
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec


@router.post("/{rec_id}/shown", response_model=RecommendationOut)
async def mark_shown(
    rec_id: uuid.UUID,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        rec = await _get_rec(rec_id, org_id, db)
        rec.is_shown = True
        await db.commit()
        await db.refresh(rec)
        return RecommendationOut.model_validate(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"mark_shown failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{rec_id}/accept", response_model=RecommendationOut)
async def accept_recommendation(
    rec_id: uuid.UUID,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        rec = await _get_rec(rec_id, org_id, db)
        rec.is_accepted = True
        await db.commit()
        await db.refresh(rec)
        return RecommendationOut.model_validate(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"accept_recommendation failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{rec_id}/reject", response_model=RecommendationOut)
async def reject_recommendation(
    rec_id: uuid.UUID,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        rec = await _get_rec(rec_id, org_id, db)
        rec.is_accepted = False
        await db.commit()
        await db.refresh(rec)
        return RecommendationOut.model_validate(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"reject_recommendation failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{rec_id}", status_code=204)
async def delete_recommendation(
    rec_id: uuid.UUID,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        rec = await _get_rec(rec_id, org_id, db)
        await db.delete(rec)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_recommendation failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")
