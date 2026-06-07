"""Cap table — shareholders, share classes, shareholdings, and dilution scenarios.

Endpoints
─────────
GET    /api/cap-table/shareholders             → list shareholders
POST   /api/cap-table/shareholders             → create
PATCH  /api/cap-table/shareholders/{id}        → update
DELETE /api/cap-table/shareholders/{id}        → delete
GET    /api/cap-table/share-classes            → list share classes
POST   /api/cap-table/share-classes            → create
GET    /api/cap-table/shareholdings            → list with joined info
POST   /api/cap-table/shareholdings            → create
DELETE /api/cap-table/shareholdings/{id}       → delete
GET    /api/cap-table/summary                  → ownership summary
GET    /api/cap-table/scenarios                → list dilution scenarios
POST   /api/cap-table/scenarios                → create scenario
GET    /api/cap-table/scenarios/{id}/model     → model dilution
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.cap_table import DilutionScenario, ShareClass, Shareholder, Shareholding

router = APIRouter(prefix="/api/cap-table", tags=["cap-table"], dependencies=[Depends(require_module("finance"))])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _shareholder_out(s: Shareholder) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "org_id": str(s.org_id),
        "name": s.name,
        "shareholder_type": s.shareholder_type,
        "email": s.email,
        "notes": s.notes,
        "created_at": s.created_at.isoformat(),
    }


def _share_class_out(sc: ShareClass) -> dict[str, Any]:
    return {
        "id": str(sc.id),
        "org_id": str(sc.org_id),
        "name": sc.name,
        "authorized_shares": sc.authorized_shares,
        "liquidation_priority": sc.liquidation_priority,
        "has_anti_dilution": sc.has_anti_dilution,
        "has_voting_rights": sc.has_voting_rights,
        "created_at": sc.created_at.isoformat(),
    }


def _shareholding_out(h: Shareholding, shareholder: Optional[Shareholder] = None, share_class: Optional[ShareClass] = None) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": str(h.id),
        "org_id": str(h.org_id),
        "shareholder_id": str(h.shareholder_id),
        "share_class_id": str(h.share_class_id),
        "shares": h.shares,
        "price_paid": float(h.price_paid) if h.price_paid is not None else None,
        "currency": h.currency,
        "grant_date": h.grant_date.isoformat() if h.grant_date else None,
        "vesting_start": h.vesting_start.isoformat() if h.vesting_start else None,
        "vesting_months": h.vesting_months,
        "cliff_months": h.cliff_months,
        "notes": h.notes,
        "created_at": h.created_at.isoformat(),
    }
    if shareholder:
        d["shareholder_name"] = shareholder.name
    if share_class:
        d["share_class_name"] = share_class.name
    return d


def _scenario_out(s: DilutionScenario) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "org_id": str(s.org_id),
        "title": s.title,
        "new_shares": s.new_shares,
        "pre_money_valuation": float(s.pre_money_valuation) if s.pre_money_valuation is not None else None,
        "currency": s.currency,
        "notes": s.notes,
        "created_at": s.created_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class ShareholderIn(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    shareholder_type: str = Field(default="other", max_length=30)
    email: Optional[str] = Field(default=None, max_length=320)
    notes: Optional[str] = None


class ShareholderPatch(BaseModel):
    name: Optional[str] = Field(default=None, max_length=300)
    shareholder_type: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=320)
    notes: Optional[str] = None


class ShareClassIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    authorized_shares: Optional[int] = None
    liquidation_priority: int = Field(default=0)
    has_anti_dilution: bool = Field(default=False)
    has_voting_rights: bool = Field(default=True)


class ShareholdingIn(BaseModel):
    shareholder_id: uuid.UUID
    share_class_id: uuid.UUID
    shares: int = Field(gt=0)
    price_paid: Optional[Decimal] = None
    currency: str = Field(default="SEK", max_length=3)
    grant_date: Optional[date] = None
    vesting_start: Optional[date] = None
    vesting_months: Optional[int] = None
    cliff_months: int = Field(default=0)
    notes: Optional[str] = None


class ScenarioIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    new_shares: int = Field(gt=0)
    pre_money_valuation: Optional[Decimal] = None
    currency: str = Field(default="SEK", max_length=3)
    notes: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/shareholders")
async def list_shareholders(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        rows = (await db.execute(
            select(Shareholder).where(Shareholder.org_id == org_id).order_by(Shareholder.name)
        )).scalars().all()
        return [_shareholder_out(s) for s in rows]
    except Exception as e:
        log.error("list_shareholders failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/shareholders", status_code=201)
async def create_shareholder(
    body: ShareholderIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        s = Shareholder(
            org_id=org_id,
            name=body.name,
            shareholder_type=body.shareholder_type,
            email=body.email,
            notes=body.notes,
        )
        db.add(s)
        await db.commit()
        await db.refresh(s)
        return _shareholder_out(s)
    except Exception as e:
        log.error("create_shareholder failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/shareholders/{shareholder_id}")
async def patch_shareholder(
    shareholder_id: uuid.UUID,
    body: ShareholderPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        s = await db.scalar(
            select(Shareholder).where(Shareholder.id == shareholder_id, Shareholder.org_id == org_id)
        )
        if not s:
            raise HTTPException(status_code=404, detail="Shareholder not found")
        if body.name is not None:
            s.name = body.name
        if body.shareholder_type is not None:
            s.shareholder_type = body.shareholder_type
        if body.email is not None:
            s.email = body.email
        if body.notes is not None:
            s.notes = body.notes
        await db.commit()
        await db.refresh(s)
        return _shareholder_out(s)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_shareholder failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/shareholders/{shareholder_id}", status_code=204)
async def delete_shareholder(
    shareholder_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        s = await db.scalar(
            select(Shareholder).where(Shareholder.id == shareholder_id, Shareholder.org_id == org_id)
        )
        if not s:
            raise HTTPException(status_code=404, detail="Shareholder not found")
        await db.delete(s)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_shareholder failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/share-classes")
async def list_share_classes(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        rows = (await db.execute(
            select(ShareClass).where(ShareClass.org_id == org_id).order_by(ShareClass.name)
        )).scalars().all()
        return [_share_class_out(sc) for sc in rows]
    except Exception as e:
        log.error("list_share_classes failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/share-classes", status_code=201)
async def create_share_class(
    body: ShareClassIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        sc = ShareClass(
            org_id=org_id,
            name=body.name,
            authorized_shares=body.authorized_shares,
            liquidation_priority=body.liquidation_priority,
            has_anti_dilution=body.has_anti_dilution,
            has_voting_rights=body.has_voting_rights,
        )
        db.add(sc)
        await db.commit()
        await db.refresh(sc)
        return _share_class_out(sc)
    except Exception as e:
        log.error("create_share_class failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/shareholdings")
async def list_shareholdings(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        holdings = (await db.execute(
            select(Shareholding).where(Shareholding.org_id == org_id).order_by(Shareholding.created_at)
        )).scalars().all()

        # Load shareholders and share classes for enrichment
        shareholder_ids = list({h.shareholder_id for h in holdings})
        share_class_ids = list({h.share_class_id for h in holdings})

        shareholders = {}
        if shareholder_ids:
            rows = (await db.execute(
                select(Shareholder).where(Shareholder.id.in_(shareholder_ids))
            )).scalars().all()
            shareholders = {s.id: s for s in rows}

        share_classes = {}
        if share_class_ids:
            rows = (await db.execute(
                select(ShareClass).where(ShareClass.id.in_(share_class_ids))
            )).scalars().all()
            share_classes = {sc.id: sc for sc in rows}

        return [
            _shareholding_out(h, shareholders.get(h.shareholder_id), share_classes.get(h.share_class_id))
            for h in holdings
        ]
    except Exception as e:
        log.error("list_shareholdings failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/shareholdings", status_code=201)
async def create_shareholding(
    body: ShareholdingIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        # Validate shareholder belongs to org
        shareholder = await db.scalar(
            select(Shareholder).where(Shareholder.id == body.shareholder_id, Shareholder.org_id == org_id)
        )
        if not shareholder:
            raise HTTPException(status_code=404, detail="Shareholder not found")

        # Validate share class belongs to org
        share_class = await db.scalar(
            select(ShareClass).where(ShareClass.id == body.share_class_id, ShareClass.org_id == org_id)
        )
        if not share_class:
            raise HTTPException(status_code=404, detail="Share class not found")

        h = Shareholding(
            org_id=org_id,
            shareholder_id=body.shareholder_id,
            share_class_id=body.share_class_id,
            shares=body.shares,
            price_paid=body.price_paid,
            currency=body.currency,
            grant_date=body.grant_date,
            vesting_start=body.vesting_start,
            vesting_months=body.vesting_months,
            cliff_months=body.cliff_months,
            notes=body.notes,
        )
        db.add(h)
        await db.commit()
        await db.refresh(h)
        return _shareholding_out(h, shareholder, share_class)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_shareholding failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/shareholdings/{shareholding_id}", status_code=204)
async def delete_shareholding(
    shareholding_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        h = await db.scalar(
            select(Shareholding).where(Shareholding.id == shareholding_id, Shareholding.org_id == org_id)
        )
        if not h:
            raise HTTPException(status_code=404, detail="Shareholding not found")
        await db.delete(h)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_shareholding failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/summary")
async def cap_table_summary(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        holdings = (await db.execute(
            select(Shareholding).where(Shareholding.org_id == org_id)
        )).scalars().all()

        total_issued = sum(h.shares for h in holdings)

        # Per shareholder totals
        shareholder_shares: dict[uuid.UUID, int] = {}
        for h in holdings:
            shareholder_shares[h.shareholder_id] = shareholder_shares.get(h.shareholder_id, 0) + h.shares

        # Per class totals
        class_shares: dict[uuid.UUID, int] = {}
        for h in holdings:
            class_shares[h.share_class_id] = class_shares.get(h.share_class_id, 0) + h.shares

        # Load shareholder names
        shareholder_names: dict[uuid.UUID, str] = {}
        if shareholder_shares:
            rows = (await db.execute(
                select(Shareholder).where(Shareholder.id.in_(list(shareholder_shares.keys())))
            )).scalars().all()
            shareholder_names = {s.id: s.name for s in rows}

        # Load share class names
        class_names: dict[uuid.UUID, str] = {}
        if class_shares:
            rows = (await db.execute(
                select(ShareClass).where(ShareClass.id.in_(list(class_shares.keys())))
            )).scalars().all()
            class_names = {sc.id: sc.name for sc in rows}

        ownership = [
            {
                "shareholder_id": str(sid),
                "shareholder_name": shareholder_names.get(sid, "Unknown"),
                "total_shares": shares,
                "ownership_pct": round(shares / total_issued * 100, 4) if total_issued else 0.0,
            }
            for sid, shares in sorted(shareholder_shares.items(), key=lambda x: x[1], reverse=True)
        ]

        by_class = [
            {
                "share_class_id": str(cid),
                "share_class_name": class_names.get(cid, "Unknown"),
                "total_shares": shares,
            }
            for cid, shares in class_shares.items()
        ]

        return {
            "total_issued_shares": total_issued,
            "total_shareholders": len(shareholder_shares),
            "by_class": by_class,
            "ownership": ownership,
        }
    except Exception as e:
        log.error("cap_table_summary failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/scenarios")
async def list_scenarios(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        rows = (await db.execute(
            select(DilutionScenario).where(DilutionScenario.org_id == org_id).order_by(DilutionScenario.created_at.desc())
        )).scalars().all()
        return [_scenario_out(s) for s in rows]
    except Exception as e:
        log.error("list_scenarios failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/scenarios", status_code=201)
async def create_scenario(
    body: ScenarioIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        s = DilutionScenario(
            org_id=org_id,
            title=body.title,
            new_shares=body.new_shares,
            pre_money_valuation=body.pre_money_valuation,
            currency=body.currency,
            notes=body.notes,
        )
        db.add(s)
        await db.commit()
        await db.refresh(s)
        return _scenario_out(s)
    except Exception as e:
        log.error("create_scenario failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/scenarios/{scenario_id}/model")
async def model_scenario(
    scenario_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        scenario = await db.scalar(
            select(DilutionScenario).where(DilutionScenario.id == scenario_id, DilutionScenario.org_id == org_id)
        )
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")

        holdings = (await db.execute(
            select(Shareholding).where(Shareholding.org_id == org_id)
        )).scalars().all()

        total_current = sum(h.shares for h in holdings)
        total_post = total_current + scenario.new_shares

        shareholder_shares: dict[uuid.UUID, int] = {}
        for h in holdings:
            shareholder_shares[h.shareholder_id] = shareholder_shares.get(h.shareholder_id, 0) + h.shares

        shareholder_names: dict[uuid.UUID, str] = {}
        if shareholder_shares:
            rows = (await db.execute(
                select(Shareholder).where(Shareholder.id.in_(list(shareholder_shares.keys())))
            )).scalars().all()
            shareholder_names = {s.id: s.name for s in rows}

        table = [
            {
                "shareholder_id": str(sid),
                "shareholder_name": shareholder_names.get(sid, "Unknown"),
                "shares": shares,
                "pre_dilution_pct": round(shares / total_current * 100, 4) if total_current else 0.0,
                "post_dilution_pct": round(shares / total_post * 100, 4) if total_post else 0.0,
            }
            for sid, shares in sorted(shareholder_shares.items(), key=lambda x: x[1], reverse=True)
        ]

        return {
            "scenario": _scenario_out(scenario),
            "pre_dilution_total_shares": total_current,
            "post_dilution_total_shares": total_post,
            "new_shares": scenario.new_shares,
            "cap_table": table,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("model_scenario failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
