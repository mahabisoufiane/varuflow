"""OKR — Objectives & Key Results with 3-level cascade.

Hierarchy: company → department → individual

Endpoints
─────────
GET    /api/okr/objectives          → list tree (top-level + children)
POST   /api/okr/objectives          → create objective
GET    /api/okr/objectives/{id}     → detail with key results
PATCH  /api/okr/objectives/{id}     → update objective
DELETE /api/okr/objectives/{id}     → delete (cascades KRs + children)
POST   /api/okr/objectives/{id}/key-results        → add key result
PATCH  /api/okr/key-results/{kr_id}               → update KR (progress / status)
DELETE /api/okr/key-results/{kr_id}               → delete KR
GET    /api/okr/progress/{period_label}            → summary dashboard for a period
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from .okr_models import OkrKeyResult, OkrObjective
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/okr", tags=["okr"], dependencies=[Depends(require_module("hr"))])
log = logging.getLogger(__name__)

_VALID_LEVELS  = {"company", "department", "individual"}
_VALID_STATUSES = {"active", "completed", "cancelled"}
_KR_STATUSES   = {"on_track", "at_risk", "off_track", "completed"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    user, _ = ctx
    return uuid.UUID(str(user["user_id"]))


def _kr_out(kr: OkrKeyResult) -> dict[str, Any]:
    progress = (
        float(kr.current_value / kr.target_value * 100)
        if kr.target_value and kr.target_value != 0 else 0.0
    )
    return {
        "id": str(kr.id),
        "objective_id": str(kr.objective_id),
        "title": kr.title,
        "target_value": float(kr.target_value),
        "current_value": float(kr.current_value),
        "unit": kr.unit,
        "status": kr.status,
        "sort_order": kr.sort_order,
        "progress_pct": round(progress, 1),
        "created_at": kr.created_at.isoformat(),
    }


def _obj_out(obj: OkrObjective, include_krs: bool = True) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": str(obj.id),
        "org_id": str(obj.org_id),
        "parent_id": str(obj.parent_id) if obj.parent_id else None,
        "owner_user_id": str(obj.owner_user_id) if obj.owner_user_id else None,
        "title": obj.title,
        "description": obj.description,
        "level": obj.level,
        "department": obj.department,
        "status": obj.status,
        "period_label": obj.period_label,
        "period_start": obj.period_start.isoformat() if obj.period_start else None,
        "period_end": obj.period_end.isoformat() if obj.period_end else None,
        "progress_pct": float(obj.progress_pct),
        "created_by_user_id": str(obj.created_by_user_id) if obj.created_by_user_id else None,
        "created_at": obj.created_at.isoformat(),
        "updated_at": obj.updated_at.isoformat(),
    }
    if include_krs:
        d["key_results"] = [_kr_out(kr) for kr in obj.key_results]
    return d


async def _recompute_progress(db: AsyncSession, obj: OkrObjective) -> None:
    """Recompute objective progress_pct from its key results."""
    krs = (await db.execute(
        select(OkrKeyResult).where(OkrKeyResult.objective_id == obj.id)
    )).scalars().all()
    if not krs:
        obj.progress_pct = Decimal("0")
        return
    total = sum(
        float(kr.current_value / kr.target_value * 100)
        for kr in krs
        if kr.target_value and kr.target_value != 0
    )
    obj.progress_pct = Decimal(str(round(total / len(krs), 2)))
    obj.updated_at = datetime.now(timezone.utc)


# ── Schemas ────────────────────────────────────────────────────────────────────

class ObjectiveIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: Optional[str] = None
    level: str = Field(default="company")
    department: Optional[str] = Field(default=None, max_length=100)
    parent_id: Optional[uuid.UUID] = None
    owner_user_id: Optional[uuid.UUID] = None
    period_label: Optional[str] = Field(default=None, max_length=20)
    period_start: Optional[date] = None
    period_end: Optional[date] = None


class ObjectivePatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=300)
    description: Optional[str] = None
    status: Optional[str] = None
    department: Optional[str] = Field(default=None, max_length=100)
    period_label: Optional[str] = Field(default=None, max_length=20)
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    owner_user_id: Optional[uuid.UUID] = None


class KeyResultIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    target_value: Decimal = Field(ge=0)
    current_value: Decimal = Field(default=Decimal("0"), ge=0)
    unit: Optional[str] = Field(default=None, max_length=30)
    sort_order: int = Field(default=0)


class KeyResultPatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=300)
    target_value: Optional[Decimal] = Field(default=None, ge=0)
    current_value: Optional[Decimal] = Field(default=None, ge=0)
    unit: Optional[str] = Field(default=None, max_length=30)
    status: Optional[str] = None
    sort_order: Optional[int] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/objectives")
async def list_objectives(
    level: Optional[str] = Query(default=None),
    department: Optional[str] = Query(default=None),
    period_label: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default="active"),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all objectives; only top-level ones include children count."""
    org_id = _org_id(ctx)
    try:
        q = select(OkrObjective).where(OkrObjective.org_id == org_id)
        if level:
            q = q.where(OkrObjective.level == level)
        if department:
            q = q.where(OkrObjective.department == department)
        if period_label:
            q = q.where(OkrObjective.period_label == period_label)
        if status:
            q = q.where(OkrObjective.status == status)
        q = q.order_by(OkrObjective.created_at)

        objs = (await db.execute(q)).scalars().all()

        # For each objective, eager-load key results
        results = []
        for obj in objs:
            krs = (await db.execute(
                select(OkrKeyResult)
                .where(OkrKeyResult.objective_id == obj.id)
                .order_by(OkrKeyResult.sort_order)
            )).scalars().all()
            obj.key_results = krs

            # Children count
            child_count = (await db.execute(
                select(OkrObjective).where(OkrObjective.parent_id == obj.id)
            )).scalars().all()
            d = _obj_out(obj, include_krs=True)
            d["child_count"] = len(child_count)
            results.append(d)
        return results
    except Exception as e:
        log.error("list_objectives failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/objectives", status_code=201)
async def create_objective(
    body: ObjectiveIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    try:
        if body.level not in _VALID_LEVELS:
            raise HTTPException(status_code=422, detail=f"level must be one of {_VALID_LEVELS}")

        # Validate parent belongs to same org
        if body.parent_id:
            parent = await db.scalar(
                select(OkrObjective).where(
                    OkrObjective.id == body.parent_id,
                    OkrObjective.org_id == org_id,
                )
            )
            if not parent:
                raise HTTPException(status_code=404, detail="Parent objective not found")

        obj = OkrObjective(
            org_id=org_id,
            parent_id=body.parent_id,
            owner_user_id=body.owner_user_id,
            title=body.title,
            description=body.description,
            level=body.level,
            department=body.department,
            period_label=body.period_label,
            period_start=body.period_start,
            period_end=body.period_end,
            created_by_user_id=user_id,
        )
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        obj.key_results = []
        return _obj_out(obj)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_objective failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/objectives/{obj_id}")
async def get_objective(
    obj_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        obj = await db.scalar(
            select(OkrObjective).where(
                OkrObjective.id == obj_id, OkrObjective.org_id == org_id
            )
        )
        if not obj:
            raise HTTPException(status_code=404, detail="Objective not found")

        krs = (await db.execute(
            select(OkrKeyResult)
            .where(OkrKeyResult.objective_id == obj.id)
            .order_by(OkrKeyResult.sort_order)
        )).scalars().all()
        obj.key_results = krs

        # children
        children = (await db.execute(
            select(OkrObjective).where(OkrObjective.parent_id == obj_id)
        )).scalars().all()
        # Load KRs for children
        for child in children:
            child_krs = (await db.execute(
                select(OkrKeyResult)
                .where(OkrKeyResult.objective_id == child.id)
                .order_by(OkrKeyResult.sort_order)
            )).scalars().all()
            child.key_results = child_krs

        result = _obj_out(obj)
        result["children"] = [_obj_out(c) for c in children]
        return result
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_objective failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/objectives/{obj_id}")
async def patch_objective(
    obj_id: uuid.UUID,
    body: ObjectivePatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        obj = await db.scalar(
            select(OkrObjective).where(
                OkrObjective.id == obj_id, OkrObjective.org_id == org_id
            )
        )
        if not obj:
            raise HTTPException(status_code=404, detail="Objective not found")

        if body.title is not None:
            obj.title = body.title
        if body.description is not None:
            obj.description = body.description
        if body.status is not None:
            if body.status not in _VALID_STATUSES:
                raise HTTPException(status_code=422, detail=f"status must be one of {_VALID_STATUSES}")
            obj.status = body.status
        if body.department is not None:
            obj.department = body.department
        if body.period_label is not None:
            obj.period_label = body.period_label
        if body.period_start is not None:
            obj.period_start = body.period_start
        if body.period_end is not None:
            obj.period_end = body.period_end
        if body.owner_user_id is not None:
            obj.owner_user_id = body.owner_user_id

        obj.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(obj)

        krs = (await db.execute(
            select(OkrKeyResult).where(OkrKeyResult.objective_id == obj.id)
        )).scalars().all()
        obj.key_results = krs
        return _obj_out(obj)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_objective failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/objectives/{obj_id}", status_code=204)
async def delete_objective(
    obj_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        obj = await db.scalar(
            select(OkrObjective).where(
                OkrObjective.id == obj_id, OkrObjective.org_id == org_id
            )
        )
        if not obj:
            raise HTTPException(status_code=404, detail="Objective not found")
        await db.delete(obj)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_objective failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Key Result endpoints ───────────────────────────────────────────────────────

@router.post("/objectives/{obj_id}/key-results", status_code=201)
async def add_key_result(
    obj_id: uuid.UUID,
    body: KeyResultIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        obj = await db.scalar(
            select(OkrObjective).where(
                OkrObjective.id == obj_id, OkrObjective.org_id == org_id
            )
        )
        if not obj:
            raise HTTPException(status_code=404, detail="Objective not found")

        kr = OkrKeyResult(
            objective_id=obj_id,
            title=body.title,
            target_value=body.target_value,
            current_value=body.current_value,
            unit=body.unit,
            sort_order=body.sort_order,
        )
        db.add(kr)
        await db.flush()

        await _recompute_progress(db, obj)
        await db.commit()
        await db.refresh(kr)
        return _kr_out(kr)
    except HTTPException:
        raise
    except Exception as e:
        log.error("add_key_result failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/key-results/{kr_id}")
async def patch_key_result(
    kr_id: uuid.UUID,
    body: KeyResultPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        kr = await db.scalar(select(OkrKeyResult).where(OkrKeyResult.id == kr_id))
        if not kr:
            raise HTTPException(status_code=404, detail="Key result not found")

        # Verify org ownership via parent objective
        obj = await db.scalar(
            select(OkrObjective).where(
                OkrObjective.id == kr.objective_id, OkrObjective.org_id == org_id
            )
        )
        if not obj:
            raise HTTPException(status_code=403, detail="Not authorised")

        if body.title is not None:
            kr.title = body.title
        if body.target_value is not None:
            kr.target_value = body.target_value
        if body.current_value is not None:
            kr.current_value = body.current_value
        if body.unit is not None:
            kr.unit = body.unit
        if body.status is not None:
            if body.status not in _KR_STATUSES:
                raise HTTPException(status_code=422, detail=f"status must be one of {_KR_STATUSES}")
            kr.status = body.status
        if body.sort_order is not None:
            kr.sort_order = body.sort_order

        kr.updated_at = datetime.now(timezone.utc)
        await db.flush()

        await _recompute_progress(db, obj)
        await db.commit()
        await db.refresh(kr)
        return _kr_out(kr)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_key_result failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/key-results/{kr_id}", status_code=204)
async def delete_key_result(
    kr_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        kr = await db.scalar(select(OkrKeyResult).where(OkrKeyResult.id == kr_id))
        if not kr:
            raise HTTPException(status_code=404, detail="Key result not found")

        obj = await db.scalar(
            select(OkrObjective).where(
                OkrObjective.id == kr.objective_id, OkrObjective.org_id == org_id
            )
        )
        if not obj:
            raise HTTPException(status_code=403, detail="Not authorised")

        await db.delete(kr)
        await db.flush()
        await _recompute_progress(db, obj)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_key_result failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Progress summary ───────────────────────────────────────────────────────────

@router.get("/progress/{period_label}")
async def okr_progress(
    period_label: str,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """High-level OKR dashboard: overall score + per-level breakdown."""
    org_id = _org_id(ctx)
    try:
        objs = (await db.execute(
            select(OkrObjective).where(
                OkrObjective.org_id == org_id,
                OkrObjective.period_label == period_label,
            )
        )).scalars().all()

        total_progress = (
            sum(float(o.progress_pct) for o in objs) / len(objs)
            if objs else 0.0
        )

        by_level: dict[str, dict] = {}
        for o in objs:
            if o.level not in by_level:
                by_level[o.level] = {"count": 0, "avg_progress": 0.0, "items": []}
            by_level[o.level]["count"] += 1
            by_level[o.level]["items"].append({
                "id": str(o.id), "title": o.title,
                "progress_pct": float(o.progress_pct), "status": o.status,
            })

        for lvl in by_level.values():
            lvl["avg_progress"] = round(
                sum(i["progress_pct"] for i in lvl["items"]) / lvl["count"], 1
            ) if lvl["count"] else 0.0

        return {
            "period_label": period_label,
            "total_objectives": len(objs),
            "overall_progress_pct": round(total_progress, 1),
            "by_level": by_level,
        }
    except Exception as e:
        log.error("okr_progress failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
