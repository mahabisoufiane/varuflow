"""Merchant customer reviews router (Sprint 12) — prefix /api/merchant-reviews."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.merchant_customer_review import MerchantCustomerReview

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/merchant-reviews", tags=["merchant-reviews"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class MerchantCustomerReviewOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    staff_user_id: uuid.UUID
    customer_id: uuid.UUID
    booking_id: Optional[uuid.UUID]
    rating: int
    body: Optional[str]
    tags: list
    is_private: bool
    shared_with_network: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CreateMerchantReviewIn(BaseModel):
    staff_user_id: uuid.UUID
    customer_id: uuid.UUID
    booking_id: Optional[uuid.UUID] = None
    rating: int = Field(..., ge=1, le=5)
    body: Optional[str] = None
    tags: list = Field(default_factory=list)
    is_private: bool = False
    shared_with_network: bool = False


class UpdateMerchantReviewIn(BaseModel):
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    body: Optional[str] = None
    tags: Optional[list] = None
    is_private: Optional[bool] = None
    shared_with_network: Optional[bool] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[MerchantCustomerReviewOut])
async def list_merchant_reviews(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    customer_id: Optional[uuid.UUID] = Query(default=None),
    rating: Optional[int] = Query(default=None, ge=1, le=5),
    shared_with_network: Optional[bool] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    try:
        org_id = _org_id(ctx)
        q = select(MerchantCustomerReview).where(MerchantCustomerReview.org_id == org_id)
        if customer_id:
            q = q.where(MerchantCustomerReview.customer_id == customer_id)
        if rating is not None:
            q = q.where(MerchantCustomerReview.rating == rating)
        if shared_with_network is not None:
            q = q.where(MerchantCustomerReview.shared_with_network == shared_with_network)
        q = q.order_by(MerchantCustomerReview.created_at.desc()).limit(limit).offset(offset)
        rows = (await db.execute(q)).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_merchant_reviews failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=MerchantCustomerReviewOut, status_code=201)
async def create_merchant_review(
    body: CreateMerchantReviewIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = MerchantCustomerReview(
            org_id=org_id,
            staff_user_id=body.staff_user_id,
            customer_id=body.customer_id,
            booking_id=body.booking_id,
            rating=body.rating,
            body=body.body,
            tags=body.tags,
            is_private=body.is_private,
            shared_with_network=body.shared_with_network,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_merchant_review failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{review_id}", response_model=MerchantCustomerReviewOut)
async def update_merchant_review(
    review_id: uuid.UUID,
    body: UpdateMerchantReviewIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(MerchantCustomerReview, review_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="Review not found")
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(record, field, value)
        record.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_merchant_review failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{review_id}", status_code=204)
async def delete_merchant_review(
    review_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(MerchantCustomerReview, review_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="Review not found")
        await db.delete(record)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_merchant_review failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/network", response_model=list[MerchantCustomerReviewOut])
async def network_merchant_reviews(
    ctx: tuple = Depends(get_current_member),  # noqa: auth required to prevent abuse
    db: AsyncSession = Depends(get_db),
    customer_id: Optional[uuid.UUID] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Cross-org read: returns reviews from OTHER orgs where shared_with_network=true."""
    try:
        org_id = _org_id(ctx)
        q = select(MerchantCustomerReview).where(
            MerchantCustomerReview.shared_with_network.is_(True),
            MerchantCustomerReview.org_id != org_id,
            MerchantCustomerReview.is_private.is_(False),
        )
        if customer_id:
            q = q.where(MerchantCustomerReview.customer_id == customer_id)
        q = q.order_by(MerchantCustomerReview.created_at.desc()).limit(limit).offset(offset)
        rows = (await db.execute(q)).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"network_merchant_reviews failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
