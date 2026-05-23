"""Investor updates — create, manage, and distribute periodic investor updates.

Endpoints
─────────
GET    /api/investor/updates                → list updates for org
POST   /api/investor/updates                → create update
GET    /api/investor/updates/dashboard      → latest update + 3-month revenue trend
GET    /api/investor/updates/{id}           → detail with recipients
PATCH  /api/investor/updates/{id}           → partial update
DELETE /api/investor/updates/{id}           → delete if draft
POST   /api/investor/updates/{id}/send      → mark sent, upsert recipients
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.investor import InvestorUpdate, InvestorUpdateRecipient

router = APIRouter(prefix="/api/investor", tags=["investor"])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    user, _ = ctx
    return uuid.UUID(str(user["user_id"]))


def _recipient_out(r: InvestorUpdateRecipient) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "update_id": str(r.update_id),
        "email": r.email,
        "name": r.name,
        "sent_at": r.sent_at.isoformat() if r.sent_at else None,
    }


def _update_out(u: InvestorUpdate, include_recipients: bool = False) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": str(u.id),
        "org_id": str(u.org_id),
        "title": u.title,
        "period_month": u.period_month.isoformat() if u.period_month else None,
        "status": u.status,
        "revenue_snapshot": float(u.revenue_snapshot) if u.revenue_snapshot is not None else None,
        "burn_rate": float(u.burn_rate) if u.burn_rate is not None else None,
        "runway_months": float(u.runway_months) if u.runway_months is not None else None,
        "key_wins": u.key_wins,
        "challenges": u.challenges,
        "next_milestones": u.next_milestones,
        "generated_pdf_url": u.generated_pdf_url,
        "sent_at": u.sent_at.isoformat() if u.sent_at else None,
        "created_by": str(u.created_by) if u.created_by else None,
        "created_at": u.created_at.isoformat(),
        "updated_at": u.updated_at.isoformat(),
    }
    if include_recipients:
        d["recipients"] = [_recipient_out(r) for r in u.recipients]
    return d


# ── Schemas ────────────────────────────────────────────────────────────────────

class UpdateIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    period_month: Optional[str] = None  # ISO date string
    revenue_snapshot: Optional[Decimal] = None
    burn_rate: Optional[Decimal] = None
    runway_months: Optional[Decimal] = None
    key_wins: Optional[str] = None
    challenges: Optional[str] = None
    next_milestones: Optional[str] = None


class UpdatePatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=300)
    period_month: Optional[str] = None
    revenue_snapshot: Optional[Decimal] = None
    burn_rate: Optional[Decimal] = None
    runway_months: Optional[Decimal] = None
    key_wins: Optional[str] = None
    challenges: Optional[str] = None
    next_milestones: Optional[str] = None
    generated_pdf_url: Optional[str] = None


class RecipientIn(BaseModel):
    email: str = Field(max_length=320)
    name: Optional[str] = Field(default=None, max_length=200)


class SendIn(BaseModel):
    recipients: list[RecipientIn] = Field(default_factory=list)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/updates")
async def list_updates(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        rows = (await db.execute(
            select(InvestorUpdate)
            .where(InvestorUpdate.org_id == org_id)
            .order_by(InvestorUpdate.period_month.desc().nullslast(), InvestorUpdate.created_at.desc())
        )).scalars().all()
        return [_update_out(u) for u in rows]
    except Exception as e:
        log.error("list_updates failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/updates", status_code=201)
async def create_update(
    body: UpdateIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    try:
        period = None
        if body.period_month:
            from datetime import date as _date
            period = _date.fromisoformat(body.period_month)

        update = InvestorUpdate(
            org_id=org_id,
            title=body.title,
            period_month=period,
            revenue_snapshot=body.revenue_snapshot,
            burn_rate=body.burn_rate,
            runway_months=body.runway_months,
            key_wins=body.key_wins,
            challenges=body.challenges,
            next_milestones=body.next_milestones,
            created_by=user_id,
        )
        db.add(update)
        await db.commit()
        await db.refresh(update)
        update.recipients = []
        return _update_out(update, include_recipients=True)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_update failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/updates/dashboard")
async def updates_dashboard(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        latest = await db.scalar(
            select(InvestorUpdate)
            .where(InvestorUpdate.org_id == org_id)
            .order_by(InvestorUpdate.period_month.desc().nullslast(), InvestorUpdate.created_at.desc())
        )
        recent = (await db.execute(
            select(InvestorUpdate)
            .where(
                InvestorUpdate.org_id == org_id,
                InvestorUpdate.revenue_snapshot.isnot(None),
            )
            .order_by(InvestorUpdate.period_month.desc().nullslast())
            .limit(3)
        )).scalars().all()

        trend = [
            {
                "period_month": u.period_month.isoformat() if u.period_month else None,
                "revenue_snapshot": float(u.revenue_snapshot) if u.revenue_snapshot else None,
            }
            for u in reversed(recent)
        ]

        return {
            "latest_update": _update_out(latest) if latest else None,
            "revenue_trend": trend,
        }
    except Exception as e:
        log.error("updates_dashboard failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/updates/{update_id}")
async def get_update(
    update_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        update = await db.scalar(
            select(InvestorUpdate).where(
                InvestorUpdate.id == update_id, InvestorUpdate.org_id == org_id
            )
        )
        if not update:
            raise HTTPException(status_code=404, detail="Investor update not found")

        recipients = (await db.execute(
            select(InvestorUpdateRecipient).where(InvestorUpdateRecipient.update_id == update_id)
        )).scalars().all()
        update.recipients = recipients
        return _update_out(update, include_recipients=True)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_update failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/updates/{update_id}")
async def patch_update(
    update_id: uuid.UUID,
    body: UpdatePatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        update = await db.scalar(
            select(InvestorUpdate).where(
                InvestorUpdate.id == update_id, InvestorUpdate.org_id == org_id
            )
        )
        if not update:
            raise HTTPException(status_code=404, detail="Investor update not found")

        if body.title is not None:
            update.title = body.title
        if body.period_month is not None:
            from datetime import date as _date
            update.period_month = _date.fromisoformat(body.period_month)
        if body.revenue_snapshot is not None:
            update.revenue_snapshot = body.revenue_snapshot
        if body.burn_rate is not None:
            update.burn_rate = body.burn_rate
        if body.runway_months is not None:
            update.runway_months = body.runway_months
        if body.key_wins is not None:
            update.key_wins = body.key_wins
        if body.challenges is not None:
            update.challenges = body.challenges
        if body.next_milestones is not None:
            update.next_milestones = body.next_milestones
        if body.generated_pdf_url is not None:
            update.generated_pdf_url = body.generated_pdf_url

        update.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(update)

        recipients = (await db.execute(
            select(InvestorUpdateRecipient).where(InvestorUpdateRecipient.update_id == update_id)
        )).scalars().all()
        update.recipients = recipients
        return _update_out(update, include_recipients=True)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_update failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/updates/{update_id}", status_code=204)
async def delete_update(
    update_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        update = await db.scalar(
            select(InvestorUpdate).where(
                InvestorUpdate.id == update_id, InvestorUpdate.org_id == org_id
            )
        )
        if not update:
            raise HTTPException(status_code=404, detail="Investor update not found")
        if update.status != "draft":
            raise HTTPException(status_code=409, detail="Only draft updates can be deleted")
        await db.delete(update)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_update failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/updates/{update_id}/send")
async def send_update(
    update_id: uuid.UUID,
    body: SendIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        update = await db.scalar(
            select(InvestorUpdate).where(
                InvestorUpdate.id == update_id, InvestorUpdate.org_id == org_id
            )
        )
        if not update:
            raise HTTPException(status_code=404, detail="Investor update not found")

        # Delete existing recipients and insert new ones
        existing = (await db.execute(
            select(InvestorUpdateRecipient).where(InvestorUpdateRecipient.update_id == update_id)
        )).scalars().all()
        for r in existing:
            await db.delete(r)
        await db.flush()

        new_recipients = []
        for r in body.recipients:
            rec = InvestorUpdateRecipient(
                update_id=update_id,
                email=r.email,
                name=r.name,
            )
            db.add(rec)
            new_recipients.append(rec)

        update.status = "sent"
        update.sent_at = datetime.now(timezone.utc)
        update.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(update)

        recipients = (await db.execute(
            select(InvestorUpdateRecipient).where(InvestorUpdateRecipient.update_id == update_id)
        )).scalars().all()
        update.recipients = recipients
        return _update_out(update, include_recipients=True)
    except HTTPException:
        raise
    except Exception as e:
        log.error("send_update failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
