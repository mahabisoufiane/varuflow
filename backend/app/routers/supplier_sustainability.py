"""Supplier Sustainability — ESG ratings for supply chain suppliers.

Endpoints
─────────
GET    /api/supplier-sustainability/summary             → counts by risk_level, avg score, unverified count
GET    /api/supplier-sustainability                     → list ratings (filter: risk_level)
POST   /api/supplier-sustainability                     → create or upsert rating
GET    /api/supplier-sustainability/{supplier_id}       → rating for a supplier (by supplier_id)
PATCH  /api/supplier-sustainability/{id}                → update rating
DELETE /api/supplier-sustainability/{id}                → delete
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.supplier_sustainability import SupplierSustainabilityRating
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/supplier-sustainability", tags=["supplier_sustainability"], dependencies=[Depends(require_module("inventory"))])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _calc_overall(env: Optional[int], social: Optional[int], gov: Optional[int]) -> Optional[int]:
    vals = [v for v in (env, social, gov) if v is not None]
    if len(vals) == 3:
        return round(sum(vals) / 3)
    return None


def _rating_out(r: SupplierSustainabilityRating) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "org_id": str(r.org_id),
        "supplier_id": str(r.supplier_id),
        "environmental_score": r.environmental_score,
        "social_score": r.social_score,
        "governance_score": r.governance_score,
        "overall_score": r.overall_score,
        "certifications": r.certifications,
        "ethical_sourcing_verified": r.ethical_sourcing_verified,
        "last_audit_date": r.last_audit_date.isoformat() if r.last_audit_date else None,
        "next_audit_date": r.next_audit_date.isoformat() if r.next_audit_date else None,
        "audit_notes": r.audit_notes,
        "risk_level": r.risk_level,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class RatingIn(BaseModel):
    supplier_id: uuid.UUID
    environmental_score: Optional[int] = Field(default=None, ge=0, le=100)
    social_score: Optional[int] = Field(default=None, ge=0, le=100)
    governance_score: Optional[int] = Field(default=None, ge=0, le=100)
    certifications: Optional[list] = None
    ethical_sourcing_verified: bool = Field(default=False)
    last_audit_date: Optional[str] = None
    next_audit_date: Optional[str] = None
    audit_notes: Optional[str] = None
    risk_level: str = Field(default="medium")


class RatingPatch(BaseModel):
    environmental_score: Optional[int] = Field(default=None, ge=0, le=100)
    social_score: Optional[int] = Field(default=None, ge=0, le=100)
    governance_score: Optional[int] = Field(default=None, ge=0, le=100)
    certifications: Optional[list] = None
    ethical_sourcing_verified: Optional[bool] = None
    last_audit_date: Optional[str] = None
    next_audit_date: Optional[str] = None
    audit_notes: Optional[str] = None
    risk_level: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/summary")
async def sustainability_summary(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        rows = (await db.execute(
            select(SupplierSustainabilityRating).where(
                SupplierSustainabilityRating.org_id == org_id
            )
        )).scalars().all()

        by_risk: dict[str, int] = {}
        scores = []
        unverified = 0
        for r in rows:
            by_risk[r.risk_level] = by_risk.get(r.risk_level, 0) + 1
            if r.overall_score is not None:
                scores.append(r.overall_score)
            if not r.ethical_sourcing_verified:
                unverified += 1

        avg_score = round(sum(scores) / len(scores), 1) if scores else None
        return {
            "total": len(rows),
            "by_risk_level": by_risk,
            "avg_overall_score": avg_score,
            "unverified_count": unverified,
        }
    except Exception as e:
        log.error("sustainability_summary failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("")
async def list_ratings(
    risk_level: Optional[str] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = select(SupplierSustainabilityRating).where(
            SupplierSustainabilityRating.org_id == org_id
        )
        if risk_level:
            q = q.where(SupplierSustainabilityRating.risk_level == risk_level)
        q = q.order_by(SupplierSustainabilityRating.created_at.desc())
        rows = (await db.execute(q)).scalars().all()
        return [_rating_out(r) for r in rows]
    except Exception as e:
        log.error("list_ratings failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def upsert_rating(
    body: RatingIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create or upsert a supplier sustainability rating."""
    org_id = _org_id(ctx)
    try:
        overall = _calc_overall(body.environmental_score, body.social_score, body.governance_score)
        now = datetime.now(timezone.utc)

        values = {
            "org_id": org_id,
            "supplier_id": body.supplier_id,
            "environmental_score": body.environmental_score,
            "social_score": body.social_score,
            "governance_score": body.governance_score,
            "overall_score": overall,
            "certifications": body.certifications or [],
            "ethical_sourcing_verified": body.ethical_sourcing_verified,
            "last_audit_date": body.last_audit_date,
            "next_audit_date": body.next_audit_date,
            "audit_notes": body.audit_notes,
            "risk_level": body.risk_level,
            "updated_at": now,
        }

        stmt = pg_insert(SupplierSustainabilityRating).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_supplier_sustainability_org_supplier",
            set_={k: v for k, v in values.items() if k not in ("org_id", "supplier_id")},
        )
        await db.execute(stmt)
        await db.commit()

        # Fetch the resulting row
        rating = await db.scalar(
            select(SupplierSustainabilityRating).where(
                SupplierSustainabilityRating.org_id == org_id,
                SupplierSustainabilityRating.supplier_id == body.supplier_id,
            )
        )
        return _rating_out(rating)
    except Exception as e:
        log.error("upsert_rating failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{supplier_id}")
async def get_rating_by_supplier(
    supplier_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        rating = await db.scalar(
            select(SupplierSustainabilityRating).where(
                SupplierSustainabilityRating.supplier_id == supplier_id,
                SupplierSustainabilityRating.org_id == org_id,
            )
        )
        if not rating:
            raise HTTPException(status_code=404, detail="Rating not found for supplier")
        return _rating_out(rating)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_rating_by_supplier failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{rating_id}")
async def patch_rating(
    rating_id: uuid.UUID,
    body: RatingPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        rating = await db.scalar(
            select(SupplierSustainabilityRating).where(
                SupplierSustainabilityRating.id == rating_id,
                SupplierSustainabilityRating.org_id == org_id,
            )
        )
        if not rating:
            raise HTTPException(status_code=404, detail="Rating not found")

        for field in (
            "environmental_score", "social_score", "governance_score",
            "certifications", "ethical_sourcing_verified",
            "last_audit_date", "next_audit_date", "audit_notes", "risk_level",
        ):
            val = getattr(body, field)
            if val is not None:
                setattr(rating, field, val)

        # Recalc overall if any score changed
        new_overall = _calc_overall(rating.environmental_score, rating.social_score, rating.governance_score)
        if new_overall is not None:
            rating.overall_score = new_overall

        rating.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(rating)
        return _rating_out(rating)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_rating failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{rating_id}", status_code=204)
async def delete_rating(
    rating_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        rating = await db.scalar(
            select(SupplierSustainabilityRating).where(
                SupplierSustainabilityRating.id == rating_id,
                SupplierSustainabilityRating.org_id == org_id,
            )
        )
        if not rating:
            raise HTTPException(status_code=404, detail="Rating not found")
        await db.delete(rating)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_rating failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
