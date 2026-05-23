"""Disputes router (Sprint 12) — prefix /api/disputes."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.dispute import Dispute, DisputeMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/disputes", tags=["disputes"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class DisputeMessageOut(BaseModel):
    id: uuid.UUID
    dispute_id: uuid.UUID
    sender_type: str
    sender_name: Optional[str]
    body: str
    attachments: Optional[dict]
    created_at: datetime

    class Config:
        from_attributes = True


class DisputeOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    booking_id: Optional[uuid.UUID]
    invoice_id: Optional[uuid.UUID]
    type: str
    status: str
    description: str
    resolution_notes: Optional[str]
    opened_by: str
    resolved_by_user_id: Optional[uuid.UUID]
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DisputeDetailOut(DisputeOut):
    messages: list[DisputeMessageOut] = []


class CreateDisputeIn(BaseModel):
    customer_id: uuid.UUID
    booking_id: Optional[uuid.UUID] = None
    invoice_id: Optional[uuid.UUID] = None
    type: str = Field(default="other", max_length=30)
    description: str
    opened_by: str = Field(default="customer", max_length=10)


class UpdateDisputeIn(BaseModel):
    resolution_notes: Optional[str] = None
    status: Optional[str] = Field(default=None, max_length=20)


class AddDisputeMessageIn(BaseModel):
    sender_type: str = Field(..., max_length=10)
    sender_name: Optional[str] = Field(default=None, max_length=100)
    body: str


class DisputeSummaryOut(BaseModel):
    by_status: dict[str, int]
    by_type: dict[str, int]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.user_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=DisputeSummaryOut)
async def get_disputes_summary(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        status_q = (
            select(Dispute.status, func.count(Dispute.id).label("cnt"))
            .where(Dispute.org_id == org_id)
            .group_by(Dispute.status)
        )
        type_q = (
            select(Dispute.type, func.count(Dispute.id).label("cnt"))
            .where(Dispute.org_id == org_id)
            .group_by(Dispute.type)
        )
        by_status = {row.status: row.cnt for row in (await db.execute(status_q)).all()}
        by_type = {row.type: row.cnt for row in (await db.execute(type_q)).all()}
        return DisputeSummaryOut(by_status=by_status, by_type=by_type)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_disputes_summary failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=list[DisputeOut])
async def list_disputes(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    customer_id: Optional[uuid.UUID] = Query(default=None),
    status: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    try:
        org_id = _org_id(ctx)
        q = select(Dispute).where(Dispute.org_id == org_id)
        if customer_id:
            q = q.where(Dispute.customer_id == customer_id)
        if status:
            q = q.where(Dispute.status == status)
        if type:
            q = q.where(Dispute.type == type)
        q = q.order_by(Dispute.created_at.desc()).limit(limit).offset(offset)
        rows = (await db.execute(q)).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_disputes failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=DisputeOut, status_code=201)
async def create_dispute(
    body: CreateDisputeIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = Dispute(
            org_id=org_id,
            customer_id=body.customer_id,
            booking_id=body.booking_id,
            invoice_id=body.invoice_id,
            type=body.type,
            description=body.description,
            opened_by=body.opened_by,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_dispute failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{dispute_id}", response_model=DisputeDetailOut)
async def get_dispute(
    dispute_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(Dispute, dispute_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="Dispute not found")
        msg_q = (
            select(DisputeMessage)
            .where(DisputeMessage.dispute_id == dispute_id)
            .order_by(DisputeMessage.created_at.asc())
        )
        messages = list((await db.execute(msg_q)).scalars().all())
        result = DisputeDetailOut.model_validate(record)
        result.messages = messages
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_dispute failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{dispute_id}", response_model=DisputeOut)
async def update_dispute(
    dispute_id: uuid.UUID,
    body: UpdateDisputeIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(Dispute, dispute_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="Dispute not found")
        if body.resolution_notes is not None:
            record.resolution_notes = body.resolution_notes
        if body.status is not None:
            record.status = body.status
        record.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_dispute failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{dispute_id}/messages", response_model=DisputeMessageOut, status_code=201)
async def add_dispute_message(
    dispute_id: uuid.UUID,
    body: AddDisputeMessageIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(Dispute, dispute_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="Dispute not found")
        msg = DisputeMessage(
            dispute_id=dispute_id,
            sender_type=body.sender_type,
            sender_name=body.sender_name,
            body=body.body,
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        return msg
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"add_dispute_message failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{dispute_id}/resolve", response_model=DisputeOut)
async def resolve_dispute(
    dispute_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(Dispute, dispute_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="Dispute not found")
        record.status = "resolved"
        record.resolved_by_user_id = _user_id(ctx)
        record.resolved_at = datetime.now(timezone.utc)
        record.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"resolve_dispute failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{dispute_id}/escalate", response_model=DisputeOut)
async def escalate_dispute(
    dispute_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(Dispute, dispute_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="Dispute not found")
        record.status = "escalated"
        record.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"escalate_dispute failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{dispute_id}/close", response_model=DisputeOut)
async def close_dispute(
    dispute_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(Dispute, dispute_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="Dispute not found")
        record.status = "closed"
        record.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"close_dispute failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
