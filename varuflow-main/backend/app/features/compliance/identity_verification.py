"""Identity verification router (Sprint 12) — prefix /api/identity-verification."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from .identity_verification_models import IdentityVerification
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/identity-verification", tags=["identity-verification"], dependencies=[Depends(require_module("hr"))])


# ── Schemas ──────────────────────────────────────────────────────────────────

class IdentityVerificationOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    booking_id: Optional[uuid.UUID]
    provider: str
    status: str
    document_type: Optional[str]
    document_ref: Optional[str]
    notes: Optional[str]
    verified_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CreateIdentityVerificationIn(BaseModel):
    customer_id: uuid.UUID
    booking_id: Optional[uuid.UUID] = None
    provider: str = Field(default="manual", max_length=30)
    document_type: Optional[str] = Field(default=None, max_length=30)
    document_ref: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = None


class UpdateIdentityVerificationIn(BaseModel):
    notes: Optional[str] = None
    document_type: Optional[str] = Field(default=None, max_length=30)
    document_ref: Optional[str] = Field(default=None, max_length=200)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[IdentityVerificationOut])
async def list_identity_verifications(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    customer_id: Optional[uuid.UUID] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    try:
        org_id = _org_id(ctx)
        q = select(IdentityVerification).where(IdentityVerification.org_id == org_id)
        if customer_id:
            q = q.where(IdentityVerification.customer_id == customer_id)
        if status:
            q = q.where(IdentityVerification.status == status)
        q = q.order_by(IdentityVerification.created_at.desc()).limit(limit).offset(offset)
        rows = (await db.execute(q)).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_identity_verifications failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=IdentityVerificationOut, status_code=201)
async def create_identity_verification(
    body: CreateIdentityVerificationIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = IdentityVerification(
            org_id=org_id,
            customer_id=body.customer_id,
            booking_id=body.booking_id,
            provider=body.provider,
            document_type=body.document_type,
            document_ref=body.document_ref,
            notes=body.notes,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_identity_verification failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{record_id}/approve", response_model=IdentityVerificationOut)
async def approve_identity_verification(
    record_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(IdentityVerification, record_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="Verification not found")
        record.status = "approved"
        record.verified_at = datetime.now(timezone.utc)
        record.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"approve_identity_verification failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{record_id}/reject", response_model=IdentityVerificationOut)
async def reject_identity_verification(
    record_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(IdentityVerification, record_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="Verification not found")
        record.status = "rejected"
        record.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"reject_identity_verification failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{record_id}", response_model=IdentityVerificationOut)
async def update_identity_verification(
    record_id: uuid.UUID,
    body: UpdateIdentityVerificationIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(IdentityVerification, record_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="Verification not found")
        if body.notes is not None:
            record.notes = body.notes
        if body.document_type is not None:
            record.document_type = body.document_type
        if body.document_ref is not None:
            record.document_ref = body.document_ref
        record.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_identity_verification failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{record_id}", status_code=204)
async def delete_identity_verification(
    record_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(IdentityVerification, record_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="Verification not found")
        await db.delete(record)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_identity_verification failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
