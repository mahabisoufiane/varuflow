"""Carbon Footprint — track Scope 1/2/3 emissions.

Endpoints
─────────
GET    /api/carbon/summary       → aggregate by scope + by category
GET    /api/carbon               → list entries (filter: scope, period)
POST   /api/carbon               → create entry
GET    /api/carbon/{id}          → detail
PATCH  /api/carbon/{id}          → update (recalcs co2_kg)
DELETE /api/carbon/{id}          → delete
POST   /api/carbon/{id}/verify   → mark as verified
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
from app.models.carbon import CarbonEntry
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/carbon", tags=["carbon"], dependencies=[Depends(require_module("analytics"))])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    user, _ = ctx
    return uuid.UUID(str(user["user_id"]))


def _calc_co2(quantity: Decimal, emission_factor: Optional[Decimal]) -> Optional[Decimal]:
    if emission_factor is not None:
        return quantity * emission_factor
    return None


def _entry_out(e: CarbonEntry) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "org_id": str(e.org_id),
        "scope": e.scope,
        "category": e.category,
        "description": e.description,
        "quantity": float(e.quantity),
        "unit": e.unit,
        "emission_factor": float(e.emission_factor) if e.emission_factor is not None else None,
        "co2_kg": float(e.co2_kg),
        "period_start": e.period_start.isoformat() if e.period_start else None,
        "period_end": e.period_end.isoformat() if e.period_end else None,
        "data_source": e.data_source,
        "verified": e.verified,
        "created_by": str(e.created_by) if e.created_by else None,
        "created_at": e.created_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class CarbonIn(BaseModel):
    scope: int = Field(ge=1, le=3)
    category: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    quantity: Decimal = Field(ge=0)
    unit: str = Field(max_length=50)
    emission_factor: Optional[Decimal] = None
    co2_kg: Optional[Decimal] = None
    period_start: date
    period_end: Optional[date] = None
    data_source: Optional[str] = Field(default=None, max_length=300)


class CarbonPatch(BaseModel):
    scope: Optional[int] = Field(default=None, ge=1, le=3)
    category: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    quantity: Optional[Decimal] = Field(default=None, ge=0)
    unit: Optional[str] = Field(default=None, max_length=50)
    emission_factor: Optional[Decimal] = None
    co2_kg: Optional[Decimal] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    data_source: Optional[str] = Field(default=None, max_length=300)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/summary")
async def carbon_summary(
    year: Optional[int] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        q = select(CarbonEntry).where(CarbonEntry.org_id == org_id)
        if year is not None:
            q = q.where(
                CarbonEntry.period_start >= date(year, 1, 1),
                CarbonEntry.period_start <= date(year, 12, 31),
            )
        rows = (await db.execute(q)).scalars().all()

        scope_totals = {1: 0.0, 2: 0.0, 3: 0.0}
        by_category: dict[str, float] = {}
        for e in rows:
            kg = float(e.co2_kg)
            scope_totals[e.scope] = scope_totals.get(e.scope, 0.0) + kg
            by_category[e.category] = by_category.get(e.category, 0.0) + kg

        total = sum(scope_totals.values())
        return {
            "scope_1_kg": round(scope_totals[1], 4),
            "scope_2_kg": round(scope_totals[2], 4),
            "scope_3_kg": round(scope_totals[3], 4),
            "total_kg": round(total, 4),
            "by_category": [
                {"category": cat, "co2_kg": round(kg, 4)}
                for cat, kg in sorted(by_category.items(), key=lambda x: -x[1])
            ],
        }
    except Exception as e:
        log.error("carbon_summary failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("")
async def list_carbon(
    scope: Optional[int] = Query(default=None),
    period_start_gte: Optional[date] = Query(default=None),
    period_start_lte: Optional[date] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = select(CarbonEntry).where(CarbonEntry.org_id == org_id)
        if scope is not None:
            q = q.where(CarbonEntry.scope == scope)
        if period_start_gte is not None:
            q = q.where(CarbonEntry.period_start >= period_start_gte)
        if period_start_lte is not None:
            q = q.where(CarbonEntry.period_start <= period_start_lte)
        q = q.order_by(CarbonEntry.period_start.desc())
        rows = (await db.execute(q)).scalars().all()
        return [_entry_out(e) for e in rows]
    except Exception as e:
        log.error("list_carbon failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_carbon(
    body: CarbonIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    try:
        co2_kg = _calc_co2(body.quantity, body.emission_factor)
        if co2_kg is None:
            if body.co2_kg is None:
                raise HTTPException(
                    status_code=422,
                    detail="Provide emission_factor or co2_kg directly.",
                )
            co2_kg = body.co2_kg

        entry = CarbonEntry(
            org_id=org_id,
            scope=body.scope,
            category=body.category,
            description=body.description,
            quantity=body.quantity,
            unit=body.unit,
            emission_factor=body.emission_factor,
            co2_kg=co2_kg,
            period_start=body.period_start,
            period_end=body.period_end,
            data_source=body.data_source,
            verified=False,
            created_by=user_id,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return _entry_out(entry)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_carbon failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{entry_id}")
async def get_carbon(
    entry_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        entry = await db.scalar(
            select(CarbonEntry).where(CarbonEntry.id == entry_id, CarbonEntry.org_id == org_id)
        )
        if not entry:
            raise HTTPException(status_code=404, detail="Carbon entry not found")
        return _entry_out(entry)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_carbon failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{entry_id}")
async def patch_carbon(
    entry_id: uuid.UUID,
    body: CarbonPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        entry = await db.scalar(
            select(CarbonEntry).where(CarbonEntry.id == entry_id, CarbonEntry.org_id == org_id)
        )
        if not entry:
            raise HTTPException(status_code=404, detail="Carbon entry not found")

        recalc = False
        if body.scope is not None:
            entry.scope = body.scope
        if body.category is not None:
            entry.category = body.category
        if body.description is not None:
            entry.description = body.description
        if body.unit is not None:
            entry.unit = body.unit
        if body.period_start is not None:
            entry.period_start = body.period_start
        if body.period_end is not None:
            entry.period_end = body.period_end
        if body.data_source is not None:
            entry.data_source = body.data_source
        if body.quantity is not None:
            entry.quantity = body.quantity
            recalc = True
        if body.emission_factor is not None:
            entry.emission_factor = body.emission_factor
            recalc = True

        if recalc:
            new_co2 = _calc_co2(entry.quantity, entry.emission_factor)
            if new_co2 is not None:
                entry.co2_kg = new_co2
        if body.co2_kg is not None and not recalc:
            entry.co2_kg = body.co2_kg

        await db.commit()
        await db.refresh(entry)
        return _entry_out(entry)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_carbon failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{entry_id}", status_code=204)
async def delete_carbon(
    entry_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        entry = await db.scalar(
            select(CarbonEntry).where(CarbonEntry.id == entry_id, CarbonEntry.org_id == org_id)
        )
        if not entry:
            raise HTTPException(status_code=404, detail="Carbon entry not found")
        await db.delete(entry)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_carbon failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{entry_id}/verify")
async def verify_carbon(
    entry_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        entry = await db.scalar(
            select(CarbonEntry).where(CarbonEntry.id == entry_id, CarbonEntry.org_id == org_id)
        )
        if not entry:
            raise HTTPException(status_code=404, detail="Carbon entry not found")
        entry.verified = True
        await db.commit()
        await db.refresh(entry)
        return _entry_out(entry)
    except HTTPException:
        raise
    except Exception as e:
        log.error("verify_carbon failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
