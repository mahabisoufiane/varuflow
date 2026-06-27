"""Vendor ratings router: manual ratings, cache, and ranking."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from .models import Supplier
from .vendor_ratings_models import VendorManualRating, VendorRatingCache
from app.middleware.plan_check import require_module

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vendor-ratings", tags=["vendor_ratings"], dependencies=[Depends(require_module("inventory"))])


def _row(obj: Any) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


# ── Schemas ──────────────────────────────────────────────────────────────────

class ManualRatingCreate(BaseModel):
    stars: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    purchase_order_id: Optional[uuid.UUID] = None
    delivery_ok: Optional[bool] = None
    quality_ok: Optional[bool] = None


class ManualRatingCreateBody(ManualRatingCreate):
    supplier_id: uuid.UUID


# ── Cache refresh helper ───────────────────────────────────────────────────────

async def _refresh_cache(db: AsyncSession, org_id: uuid.UUID, supplier_id: uuid.UUID) -> VendorRatingCache:
    """Recompute and upsert vendor_rating_cache from manual ratings."""
    ratings = (await db.execute(
        select(VendorManualRating).where(
            VendorManualRating.org_id == org_id,
            VendorManualRating.supplier_id == supplier_id,
        )
    )).scalars().all()

    po_count = len(ratings)

    if not ratings:
        on_time_rate = Decimal("0")
        quality_score = Decimal("0")
        manual_avg = Decimal("0")
    else:
        delivery_rated = [r for r in ratings if r.delivery_ok is not None]
        on_time_rate = (
            Decimal(str(sum(1 for r in delivery_rated if r.delivery_ok) / len(delivery_rated) * 100)).quantize(Decimal("0.01"))
            if delivery_rated else Decimal("0")
        )

        quality_rated = [r for r in ratings if r.quality_ok is not None]
        quality_score = (
            Decimal(str(sum(1 for r in quality_rated if r.quality_ok) / len(quality_rated) * 100)).quantize(Decimal("0.01"))
            if quality_rated else Decimal("0")
        )

        manual_avg = (
            Decimal(str(sum(r.stars for r in ratings) / len(ratings))).quantize(Decimal("0.01"))
        )

    price_stability = Decimal("80")  # stubbed — real computation requires PO price history

    # overall_score = on_time*0.35 + quality*0.25 + price_stability*0.20 + manual_avg_normalized*20*0.20
    manual_avg_normalized = manual_avg / Decimal("5") * Decimal("100")
    overall_score = (
        on_time_rate * Decimal("0.35")
        + quality_score * Decimal("0.25")
        + price_stability * Decimal("0.20")
        + manual_avg_normalized * Decimal("20") * Decimal("0.20")
    ).quantize(Decimal("0.01"))

    # Upsert via select + update or insert
    existing = (await db.execute(
        select(VendorRatingCache).where(
            VendorRatingCache.org_id == org_id,
            VendorRatingCache.supplier_id == supplier_id,
        )
    )).scalar_one_or_none()

    if existing:
        existing.on_time_rate = on_time_rate
        existing.quality_score = quality_score
        existing.price_stability = price_stability
        existing.manual_avg = manual_avg
        existing.overall_score = overall_score
        existing.po_count = po_count
        existing.last_updated = datetime.now(timezone.utc)
        cache = existing
    else:
        cache = VendorRatingCache(
            org_id=org_id,
            supplier_id=supplier_id,
            on_time_rate=on_time_rate,
            quality_score=quality_score,
            price_stability=price_stability,
            manual_avg=manual_avg,
            overall_score=overall_score,
            po_count=po_count,
        )
        db.add(cache)

    await db.flush()
    return cache


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/ranking")
async def vendor_ranking(
    category: Optional[str] = None,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """List all suppliers ranked by overall_score DESC."""
    user, member = auth
    org_id = member.org_id
    try:
        caches = (await db.execute(
            select(VendorRatingCache).where(VendorRatingCache.org_id == org_id)
            .order_by(VendorRatingCache.overall_score.desc())
        )).scalars().all()

        result = []
        for cache in caches:
            supplier = (await db.execute(
                select(Supplier).where(Supplier.id == cache.supplier_id)
            )).scalar_one_or_none()
            entry = _row(cache)
            entry["supplier_name"] = supplier.name if supplier else None
            result.append(entry)

        return result
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"vendor_ranking failed: {e}", extra={"org_id": org_id})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("")
async def list_vendor_ratings(
    sort_by: Optional[str] = Query(None, pattern="^(overall_score|on_time_rate|quality_score)$"),
    min_score: Optional[float] = None,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """List all manual ratings (history) for this org, most recent first."""
    user, member = auth
    org_id = member.org_id
    try:
        ratings = (await db.execute(
            select(VendorManualRating)
            .where(VendorManualRating.org_id == org_id)
            .order_by(VendorManualRating.created_at.desc())
            .limit(200)
        )).scalars().all()
        return [_row(r) for r in ratings]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_vendor_ratings failed: {e}", extra={"org_id": org_id})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def add_manual_rating_body(
    body: ManualRatingCreateBody,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Add a manual rating with supplier_id in request body, then refresh cache."""
    user, member = auth
    org_id = member.org_id
    try:
        supplier = (await db.execute(
            select(Supplier).where(Supplier.id == body.supplier_id, Supplier.org_id == org_id)
        )).scalar_one_or_none()
        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier not found")

        rating = VendorManualRating(
            org_id=org_id,
            supplier_id=body.supplier_id,
            purchase_order_id=body.purchase_order_id,
            stars=body.stars,
            comment=body.comment,
            rated_by_staff_id=user.get("user_id"),
            delivery_ok=body.delivery_ok,
            quality_ok=body.quality_ok,
        )
        db.add(rating)
        await db.flush()

        await _refresh_cache(db, org_id, body.supplier_id)
        await db.commit()
        await db.refresh(rating)
        return _row(rating)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"add_manual_rating_body failed: {e}", extra={"org_id": org_id})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{supplier_id}")
async def get_vendor_rating(
    supplier_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Get rating cache for one supplier. Returns stub with zeros if no cache."""
    user, member = auth
    org_id = member.org_id
    try:
        cache = (await db.execute(
            select(VendorRatingCache).where(
                VendorRatingCache.org_id == org_id,
                VendorRatingCache.supplier_id == supplier_id,
            )
        )).scalar_one_or_none()

        if cache:
            return _row(cache)

        # Return computed stub with zeros
        return {
            "org_id": str(org_id),
            "supplier_id": str(supplier_id),
            "on_time_rate": 0,
            "quality_score": 0,
            "price_stability": 0,
            "manual_avg": 0,
            "overall_score": 0,
            "po_count": 0,
            "last_updated": None,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"get_vendor_rating failed: {e}", extra={"org_id": org_id})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{supplier_id}/rate", status_code=201)
async def add_manual_rating(
    supplier_id: uuid.UUID,
    body: ManualRatingCreate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Add a manual rating for a supplier, then refresh cache."""
    user, member = auth
    org_id = member.org_id
    try:
        rating = VendorManualRating(
            org_id=org_id,
            supplier_id=supplier_id,
            purchase_order_id=body.purchase_order_id,
            stars=body.stars,
            comment=body.comment,
            rated_by_staff_id=user.get("user_id"),
            delivery_ok=body.delivery_ok,
            quality_ok=body.quality_ok,
        )
        db.add(rating)
        await db.flush()

        await _refresh_cache(db, org_id, supplier_id)
        await db.commit()
        await db.refresh(rating)
        return _row(rating)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"add_manual_rating failed: {e}", extra={"org_id": org_id})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{supplier_id}/reviews")
async def list_reviews(
    supplier_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """List manual ratings for this supplier, most recent first, limit 50."""
    user, member = auth
    org_id = member.org_id
    try:
        ratings = (await db.execute(
            select(VendorManualRating).where(
                VendorManualRating.org_id == org_id,
                VendorManualRating.supplier_id == supplier_id,
            ).order_by(VendorManualRating.created_at.desc()).limit(50)
        )).scalars().all()
        return [_row(r) for r in ratings]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_reviews failed: {e}", extra={"org_id": org_id})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{supplier_id}/refresh")
async def refresh_cache(
    supplier_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Recompute and save the vendor_rating_cache from manual ratings."""
    user, member = auth
    org_id = member.org_id
    try:
        cache = await _refresh_cache(db, org_id, supplier_id)
        await db.commit()
        await db.refresh(cache)
        return _row(cache)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"refresh_cache failed: {e}", extra={"org_id": org_id})
        raise HTTPException(status_code=500, detail="Internal server error")
