"""Risk Register — track and manage organisational risks.

Endpoints
─────────
GET    /api/risk/summary         → counts by status/category + avg score
GET    /api/risk                 → list risks (filter: status, category)
POST   /api/risk                 → create risk item
GET    /api/risk/{id}            → detail
PATCH  /api/risk/{id}            → partial update (recalcs score if likelihood/impact change)
DELETE /api/risk/{id}            → delete
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from .risk import RiskItem

router = APIRouter(prefix="/api/risk", tags=["risk_register"], dependencies=[Depends(require_module("compliance"))])
log = logging.getLogger(__name__)

_LIKELIHOOD_MAP = {"low": 1, "medium": 2, "high": 3, "critical": 4}
_IMPACT_MAP = {"low": 1, "medium": 2, "high": 3, "critical": 4}
_VALID_STATUSES = {"identified", "monitoring", "mitigating", "resolved", "accepted"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    user, _ = ctx
    return uuid.UUID(str(user["user_id"]))


def _calc_risk_score(likelihood: str, impact: str) -> Decimal:
    l_val = _LIKELIHOOD_MAP.get(likelihood, 2)
    i_val = _IMPACT_MAP.get(impact, 2)
    return Decimal(str(float(l_val * i_val)))


def _risk_out(r: RiskItem) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "org_id": str(r.org_id),
        "title": r.title,
        "category": r.category,
        "description": r.description,
        "likelihood": r.likelihood,
        "impact": r.impact,
        "risk_score": float(r.risk_score) if r.risk_score is not None else None,
        "status": r.status,
        "mitigation_plan": r.mitigation_plan,
        "owner_user_id": str(r.owner_user_id) if r.owner_user_id else None,
        "due_date": r.due_date.isoformat() if r.due_date else None,
        "last_reviewed": r.last_reviewed.isoformat() if r.last_reviewed else None,
        "created_by": str(r.created_by) if r.created_by else None,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class RiskIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    category: str = Field(default="other", max_length=100)
    description: Optional[str] = None
    likelihood: str = Field(default="medium")
    impact: str = Field(default="medium")
    mitigation_plan: Optional[str] = None
    owner_user_id: Optional[uuid.UUID] = None
    due_date: Optional[str] = None


class RiskPatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=300)
    category: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    likelihood: Optional[str] = None
    impact: Optional[str] = None
    mitigation_plan: Optional[str] = None
    owner_user_id: Optional[uuid.UUID] = None
    due_date: Optional[str] = None
    last_reviewed: Optional[str] = None
    status: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/summary")
async def risk_summary(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Returns counts by status, counts by category, and avg risk_score."""
    org_id = _org_id(ctx)
    try:
        rows = (await db.execute(
            select(RiskItem).where(RiskItem.org_id == org_id)
        )).scalars().all()

        by_status: dict[str, int] = {}
        by_category: dict[str, int] = {}
        scores = []
        for r in rows:
            by_status[r.status] = by_status.get(r.status, 0) + 1
            by_category[r.category] = by_category.get(r.category, 0) + 1
            if r.risk_score is not None:
                scores.append(float(r.risk_score))

        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        return {
            "total": len(rows),
            "by_status": by_status,
            "by_category": by_category,
            "avg_risk_score": avg_score,
        }
    except Exception as e:
        log.error("risk_summary failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("")
async def list_risks(
    status: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = select(RiskItem).where(RiskItem.org_id == org_id)
        if status:
            q = q.where(RiskItem.status == status)
        if category:
            q = q.where(RiskItem.category == category)
        q = q.order_by(RiskItem.created_at.desc())
        rows = (await db.execute(q)).scalars().all()
        return [_risk_out(r) for r in rows]
    except Exception as e:
        log.error("list_risks failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_risk(
    body: RiskIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    try:
        if body.likelihood not in _LIKELIHOOD_MAP:
            raise HTTPException(status_code=422, detail=f"likelihood must be one of {list(_LIKELIHOOD_MAP)}")
        if body.impact not in _IMPACT_MAP:
            raise HTTPException(status_code=422, detail=f"impact must be one of {list(_IMPACT_MAP)}")

        risk_score = _calc_risk_score(body.likelihood, body.impact)
        item = RiskItem(
            org_id=org_id,
            title=body.title,
            category=body.category,
            description=body.description,
            likelihood=body.likelihood,
            impact=body.impact,
            risk_score=risk_score,
            status="identified",
            mitigation_plan=body.mitigation_plan,
            owner_user_id=body.owner_user_id,
            due_date=body.due_date,
            created_by=user_id,
        )
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return _risk_out(item)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_risk failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{item_id}")
async def get_risk(
    item_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        item = await db.scalar(
            select(RiskItem).where(RiskItem.id == item_id, RiskItem.org_id == org_id)
        )
        if not item:
            raise HTTPException(status_code=404, detail="Risk item not found")
        return _risk_out(item)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_risk failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{item_id}")
async def patch_risk(
    item_id: uuid.UUID,
    body: RiskPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        item = await db.scalar(
            select(RiskItem).where(RiskItem.id == item_id, RiskItem.org_id == org_id)
        )
        if not item:
            raise HTTPException(status_code=404, detail="Risk item not found")

        if body.title is not None:
            item.title = body.title
        if body.category is not None:
            item.category = body.category
        if body.description is not None:
            item.description = body.description
        if body.mitigation_plan is not None:
            item.mitigation_plan = body.mitigation_plan
        if body.owner_user_id is not None:
            item.owner_user_id = body.owner_user_id
        if body.due_date is not None:
            item.due_date = body.due_date
        if body.last_reviewed is not None:
            item.last_reviewed = body.last_reviewed
        if body.status is not None:
            if body.status not in _VALID_STATUSES:
                raise HTTPException(status_code=422, detail=f"status must be one of {_VALID_STATUSES}")
            item.status = body.status

        recalc = False
        if body.likelihood is not None:
            if body.likelihood not in _LIKELIHOOD_MAP:
                raise HTTPException(status_code=422, detail=f"likelihood must be one of {list(_LIKELIHOOD_MAP)}")
            item.likelihood = body.likelihood
            recalc = True
        if body.impact is not None:
            if body.impact not in _IMPACT_MAP:
                raise HTTPException(status_code=422, detail=f"impact must be one of {list(_IMPACT_MAP)}")
            item.impact = body.impact
            recalc = True
        if recalc:
            item.risk_score = _calc_risk_score(item.likelihood, item.impact)

        item.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(item)
        return _risk_out(item)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_risk failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{item_id}", status_code=204)
async def delete_risk(
    item_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        item = await db.scalar(
            select(RiskItem).where(RiskItem.id == item_id, RiskItem.org_id == org_id)
        )
        if not item:
            raise HTTPException(status_code=404, detail="Risk item not found")
        await db.delete(item)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_risk failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
