"""Service reviews router (Sprint 11) — prefix /api/service-reviews."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.service_review import ServiceReview
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/service-reviews", tags=["service-reviews"], dependencies=[Depends(require_module("analytics"))])


# ── Schemas ──────────────────────────────────────────────────────────────────

class ServiceReviewOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    booking_id: Optional[uuid.UUID]
    product_id: Optional[uuid.UUID]
    service_id: Optional[uuid.UUID]
    staff_id: Optional[uuid.UUID]
    reviewer_name: Optional[str]
    rating: int
    body: Optional[str]
    is_verified_purchase: bool
    is_published: bool
    reply_text: Optional[str]
    replied_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CreateServiceReviewIn(BaseModel):
    customer_id: uuid.UUID
    booking_id: Optional[uuid.UUID] = None
    product_id: Optional[uuid.UUID] = None
    service_id: Optional[uuid.UUID] = None
    staff_id: Optional[uuid.UUID] = None
    reviewer_name: Optional[str] = Field(default=None, max_length=100)
    rating: int = Field(..., ge=1, le=5)
    body: Optional[str] = None


class UpdateServiceReviewIn(BaseModel):
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    body: Optional[str] = None


class ReplyIn(BaseModel):
    reply_text: str


class TogglePublishIn(BaseModel):
    is_published: bool


class ReviewSummaryOut(BaseModel):
    average_rating: float
    total_count: int
    breakdown: dict[int, int]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=ReviewSummaryOut)
async def get_reviews_summary(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    service_id: Optional[uuid.UUID] = Query(default=None),
    staff_id: Optional[uuid.UUID] = Query(default=None),
):
    """Return avg rating, total count, and per-star breakdown."""
    try:
        org_id = _org_id(ctx)
        q = select(ServiceReview.rating).where(
            ServiceReview.org_id == org_id,
            ServiceReview.is_published.is_(True),
        )
        if service_id:
            q = q.where(ServiceReview.service_id == service_id)
        if staff_id:
            q = q.where(ServiceReview.staff_id == staff_id)
        ratings = list((await db.execute(q)).scalars().all())
        total = len(ratings)
        avg = round(sum(ratings) / total, 2) if total else 0.0
        breakdown = {i: ratings.count(i) for i in range(1, 6)}
        return ReviewSummaryOut(average_rating=avg, total_count=total, breakdown=breakdown)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_reviews_summary failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=list[ServiceReviewOut])
async def list_service_reviews(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    service_id: Optional[uuid.UUID] = Query(default=None),
    staff_id: Optional[uuid.UUID] = Query(default=None),
    rating: Optional[int] = Query(default=None, ge=1, le=5),
    is_verified: Optional[bool] = Query(default=None),
    is_published: Optional[bool] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    try:
        org_id = _org_id(ctx)
        q = select(ServiceReview).where(ServiceReview.org_id == org_id)
        if service_id:
            q = q.where(ServiceReview.service_id == service_id)
        if staff_id:
            q = q.where(ServiceReview.staff_id == staff_id)
        if rating is not None:
            q = q.where(ServiceReview.rating == rating)
        if is_verified is not None:
            q = q.where(ServiceReview.is_verified_purchase == is_verified)
        if is_published is not None:
            q = q.where(ServiceReview.is_published == is_published)
        q = q.order_by(ServiceReview.created_at.desc()).limit(limit).offset(offset)
        rows = (await db.execute(q)).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_service_reviews failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=ServiceReviewOut, status_code=201)
async def create_service_review(
    body: CreateServiceReviewIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        is_verified = False
        if body.booking_id:
            from app.models.bookings import Appointment
            appt = await db.get(Appointment, body.booking_id)
            if appt and appt.org_id == org_id and str(appt.customer_id) == str(body.customer_id):
                is_verified = True
        review = ServiceReview(
            org_id=org_id,
            customer_id=body.customer_id,
            booking_id=body.booking_id,
            product_id=body.product_id,
            service_id=body.service_id,
            staff_id=body.staff_id,
            reviewer_name=body.reviewer_name,
            rating=body.rating,
            body=body.body,
            is_verified_purchase=is_verified,
        )
        db.add(review)
        await db.commit()
        await db.refresh(review)
        return review
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_service_review failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{review_id}", response_model=ServiceReviewOut)
async def update_service_review(
    review_id: uuid.UUID,
    body: UpdateServiceReviewIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        review = await db.get(ServiceReview, review_id)
        if not review or review.org_id != org_id:
            raise HTTPException(status_code=404, detail="Review not found")
        if body.rating is not None:
            review.rating = body.rating
        if body.body is not None:
            review.body = body.body
        review.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(review)
        return review
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_service_review failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{review_id}/reply", response_model=ServiceReviewOut)
async def reply_to_review(
    review_id: uuid.UUID,
    body: ReplyIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        review = await db.get(ServiceReview, review_id)
        if not review or review.org_id != org_id:
            raise HTTPException(status_code=404, detail="Review not found")
        review.reply_text = body.reply_text
        review.replied_at = datetime.now(timezone.utc)
        review.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(review)
        return review
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"reply_to_review failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{review_id}/publish", response_model=ServiceReviewOut)
async def toggle_publish(
    review_id: uuid.UUID,
    body: TogglePublishIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        review = await db.get(ServiceReview, review_id)
        if not review or review.org_id != org_id:
            raise HTTPException(status_code=404, detail="Review not found")
        review.is_published = body.is_published
        review.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(review)
        return review
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"toggle_publish failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{review_id}", status_code=204)
async def delete_service_review(
    review_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        review = await db.get(ServiceReview, review_id)
        if not review or review.org_id != org_id:
            raise HTTPException(status_code=404, detail="Review not found")
        await db.delete(review)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_service_review failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
