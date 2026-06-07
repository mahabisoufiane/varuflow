"""Board packs — meeting materials with KPI snapshots.

Endpoints
─────────
GET    /api/board-packs                    → list packs
POST   /api/board-packs                    → create
GET    /api/board-packs/{id}               → detail
PATCH  /api/board-packs/{id}               → update
DELETE /api/board-packs/{id}               → delete if draft
POST   /api/board-packs/{id}/publish       → publish
POST   /api/board-packs/{id}/auto-populate → pull KPIs from recent data
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.board_pack import BoardPack
from app.models.invoicing import Customer, Invoice

router = APIRouter(prefix="/api/board-packs", tags=["board-packs"], dependencies=[Depends(require_module("finance"))])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    user, _ = ctx
    return uuid.UUID(str(user["user_id"]))


def _pack_out(p: BoardPack) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "org_id": str(p.org_id),
        "title": p.title,
        "meeting_date": p.meeting_date.isoformat() if p.meeting_date else None,
        "status": p.status,
        "financial_period": p.financial_period,
        "agenda": p.agenda,
        "executive_summary": p.executive_summary,
        "kpi_snapshot": p.kpi_snapshot,
        "pdf_url": p.pdf_url,
        "notes": p.notes,
        "created_by": str(p.created_by) if p.created_by else None,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class PackIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    meeting_date: Optional[date] = None
    financial_period: Optional[str] = Field(default=None, max_length=50)
    agenda: Optional[str] = None
    executive_summary: Optional[str] = None
    notes: Optional[str] = None


class PackPatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=300)
    meeting_date: Optional[date] = None
    financial_period: Optional[str] = Field(default=None, max_length=50)
    agenda: Optional[str] = None
    executive_summary: Optional[str] = None
    kpi_snapshot: Optional[dict] = None
    pdf_url: Optional[str] = None
    notes: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_packs(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        rows = (await db.execute(
            select(BoardPack)
            .where(BoardPack.org_id == org_id)
            .order_by(BoardPack.meeting_date.desc().nullslast())
        )).scalars().all()
        return [_pack_out(p) for p in rows]
    except Exception as e:
        log.error("list_packs failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_pack(
    body: PackIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    try:
        p = BoardPack(
            org_id=org_id,
            title=body.title,
            meeting_date=body.meeting_date,
            financial_period=body.financial_period,
            agenda=body.agenda,
            executive_summary=body.executive_summary,
            notes=body.notes,
            created_by=user_id,
        )
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return _pack_out(p)
    except Exception as e:
        log.error("create_pack failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{pack_id}")
async def get_pack(
    pack_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        p = await db.scalar(
            select(BoardPack).where(BoardPack.id == pack_id, BoardPack.org_id == org_id)
        )
        if not p:
            raise HTTPException(status_code=404, detail="Board pack not found")
        return _pack_out(p)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_pack failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{pack_id}")
async def patch_pack(
    pack_id: uuid.UUID,
    body: PackPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        p = await db.scalar(
            select(BoardPack).where(BoardPack.id == pack_id, BoardPack.org_id == org_id)
        )
        if not p:
            raise HTTPException(status_code=404, detail="Board pack not found")

        if body.title is not None:
            p.title = body.title
        if body.meeting_date is not None:
            p.meeting_date = body.meeting_date
        if body.financial_period is not None:
            p.financial_period = body.financial_period
        if body.agenda is not None:
            p.agenda = body.agenda
        if body.executive_summary is not None:
            p.executive_summary = body.executive_summary
        if body.kpi_snapshot is not None:
            p.kpi_snapshot = body.kpi_snapshot
        if body.pdf_url is not None:
            p.pdf_url = body.pdf_url
        if body.notes is not None:
            p.notes = body.notes

        p.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(p)
        return _pack_out(p)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_pack failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{pack_id}", status_code=204)
async def delete_pack(
    pack_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        p = await db.scalar(
            select(BoardPack).where(BoardPack.id == pack_id, BoardPack.org_id == org_id)
        )
        if not p:
            raise HTTPException(status_code=404, detail="Board pack not found")
        if p.status != "draft":
            raise HTTPException(status_code=409, detail="Only draft board packs can be deleted")
        await db.delete(p)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_pack failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{pack_id}/publish")
async def publish_pack(
    pack_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        p = await db.scalar(
            select(BoardPack).where(BoardPack.id == pack_id, BoardPack.org_id == org_id)
        )
        if not p:
            raise HTTPException(status_code=404, detail="Board pack not found")
        p.status = "published"
        p.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(p)
        return _pack_out(p)
    except HTTPException:
        raise
    except Exception as e:
        log.error("publish_pack failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{pack_id}/auto-populate")
async def auto_populate_pack(
    pack_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        p = await db.scalar(
            select(BoardPack).where(BoardPack.id == pack_id, BoardPack.org_id == org_id)
        )
        if not p:
            raise HTTPException(status_code=404, detail="Board pack not found")

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)

        # Sum of invoice totals in last 30 days
        invoice_total_row = await db.execute(
            select(func.coalesce(func.sum(Invoice.total_sek), 0))
            .where(Invoice.org_id == org_id, Invoice.created_at >= cutoff)
        )
        invoice_total = float(invoice_total_row.scalar() or 0)

        # Total customer count
        customer_count_row = await db.execute(
            select(func.count(Customer.id)).where(Customer.org_id == org_id)
        )
        customer_count = int(customer_count_row.scalar() or 0)

        kpi_snapshot = {
            "revenue_last_30_days": invoice_total,
            "total_customers": customer_count,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        p.kpi_snapshot = kpi_snapshot
        p.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(p)
        return _pack_out(p)
    except HTTPException:
        raise
    except Exception as e:
        log.error("auto_populate_pack failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
