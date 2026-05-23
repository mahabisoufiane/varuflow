"""Decision Log — structured record of organisational decisions.

Endpoints
─────────
GET    /api/decisions/stats     → aggregate counts by area/status + last 90 days
GET    /api/decisions           → list decisions (filter area/status)
POST   /api/decisions           → create decision entry
GET    /api/decisions/{id}      → detail
PATCH  /api/decisions/{id}      → update any field
DELETE /api/decisions/{id}      → delete
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.decision_log import DecisionEntry

router = APIRouter(prefix="/api/decisions", tags=["decisions"])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    user, _ = ctx
    return uuid.UUID(str(user["user_id"]))


def _entry_out(e: DecisionEntry) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "org_id": str(e.org_id),
        "title": e.title,
        "decided_at": e.decided_at.isoformat(),
        "decided_by_user_id": str(e.decided_by_user_id) if e.decided_by_user_id else None,
        "decided_by_name": e.decided_by_name,
        "area": e.area,
        "decision_summary": e.decision_summary,
        "alternatives_considered": e.alternatives_considered,
        "expected_outcome": e.expected_outcome,
        "actual_outcome": e.actual_outcome,
        "status": e.status,
        "created_by": str(e.created_by) if e.created_by else None,
        "created_at": e.created_at.isoformat(),
        "updated_at": e.updated_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class DecisionIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    decided_at: date
    decided_by_user_id: Optional[uuid.UUID] = None
    decided_by_name: Optional[str] = Field(default=None, max_length=200)
    area: Optional[str] = Field(default=None, max_length=100)
    decision_summary: str = Field(min_length=1)
    alternatives_considered: Optional[str] = None
    expected_outcome: Optional[str] = None
    actual_outcome: Optional[str] = None
    status: str = Field(default="pending")


class DecisionPatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=300)
    decided_at: Optional[date] = None
    decided_by_user_id: Optional[uuid.UUID] = None
    decided_by_name: Optional[str] = Field(default=None, max_length=200)
    area: Optional[str] = Field(default=None, max_length=100)
    decision_summary: Optional[str] = None
    alternatives_considered: Optional[str] = None
    expected_outcome: Optional[str] = None
    actual_outcome: Optional[str] = None
    status: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/stats")
async def decision_stats(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Aggregate counts: total, by_area, by_status, last_90_days_count."""
    org_id = _org_id(ctx)
    try:
        entries = (await db.execute(
            select(DecisionEntry).where(DecisionEntry.org_id == org_id)
        )).scalars().all()

        total = len(entries)
        by_area: dict[str, int] = {}
        by_status: dict[str, int] = {}
        cutoff = date.today() - timedelta(days=90)
        last_90 = 0

        for e in entries:
            area_key = e.area or "other"
            by_area[area_key] = by_area.get(area_key, 0) + 1
            by_status[e.status] = by_status.get(e.status, 0) + 1
            if e.decided_at >= cutoff:
                last_90 += 1

        return {
            "total": total,
            "by_area": by_area,
            "by_status": by_status,
            "last_90_days_count": last_90,
        }
    except Exception as e:
        log.error("decision_stats failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("")
async def list_decisions(
    area: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = select(DecisionEntry).where(DecisionEntry.org_id == org_id)
        if area:
            q = q.where(DecisionEntry.area == area)
        if status:
            q = q.where(DecisionEntry.status == status)
        q = q.order_by(DecisionEntry.decided_at.desc())
        entries = (await db.execute(q)).scalars().all()
        return [_entry_out(e) for e in entries]
    except Exception as e:
        log.error("list_decisions failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_decision(
    body: DecisionIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    try:
        entry = DecisionEntry(
            org_id=org_id,
            title=body.title,
            decided_at=body.decided_at,
            decided_by_user_id=body.decided_by_user_id if body.decided_by_user_id else user_id,
            decided_by_name=body.decided_by_name,
            area=body.area,
            decision_summary=body.decision_summary,
            alternatives_considered=body.alternatives_considered,
            expected_outcome=body.expected_outcome,
            actual_outcome=body.actual_outcome,
            status=body.status,
            created_by=user_id,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return _entry_out(entry)
    except Exception as e:
        log.error("create_decision failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{entry_id}")
async def get_decision(
    entry_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        entry = await db.scalar(
            select(DecisionEntry).where(
                DecisionEntry.id == entry_id, DecisionEntry.org_id == org_id
            )
        )
        if not entry:
            raise HTTPException(status_code=404, detail="Decision entry not found")
        return _entry_out(entry)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_decision failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{entry_id}")
async def patch_decision(
    entry_id: uuid.UUID,
    body: DecisionPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        entry = await db.scalar(
            select(DecisionEntry).where(
                DecisionEntry.id == entry_id, DecisionEntry.org_id == org_id
            )
        )
        if not entry:
            raise HTTPException(status_code=404, detail="Decision entry not found")

        if body.title is not None:
            entry.title = body.title
        if body.decided_at is not None:
            entry.decided_at = body.decided_at
        if body.decided_by_user_id is not None:
            entry.decided_by_user_id = body.decided_by_user_id
        if body.decided_by_name is not None:
            entry.decided_by_name = body.decided_by_name
        if body.area is not None:
            entry.area = body.area
        if body.decision_summary is not None:
            entry.decision_summary = body.decision_summary
        if body.alternatives_considered is not None:
            entry.alternatives_considered = body.alternatives_considered
        if body.expected_outcome is not None:
            entry.expected_outcome = body.expected_outcome
        if body.actual_outcome is not None:
            entry.actual_outcome = body.actual_outcome
        if body.status is not None:
            entry.status = body.status

        entry.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(entry)
        return _entry_out(entry)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_decision failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{entry_id}", status_code=204)
async def delete_decision(
    entry_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        entry = await db.scalar(
            select(DecisionEntry).where(
                DecisionEntry.id == entry_id, DecisionEntry.org_id == org_id
            )
        )
        if not entry:
            raise HTTPException(status_code=404, detail="Decision entry not found")
        await db.delete(entry)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_decision failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
