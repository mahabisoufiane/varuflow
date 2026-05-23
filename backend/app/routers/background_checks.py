"""Background checks router (Sprint 12) — prefix /api/background-checks."""
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
from app.models.staff_background_check import StaffBackgroundCheck

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/background-checks", tags=["background-checks"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class BackgroundCheckOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    staff_id: uuid.UUID
    provider: Optional[str]
    check_type: str
    status: str
    issued_date: Optional[datetime]
    expiry_date: Optional[datetime]
    badge_visible: bool
    reference_number: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PublicBackgroundCheckOut(BaseModel):
    check_type: str
    status: str
    issued_date: Optional[datetime]
    badge_visible: bool

    class Config:
        from_attributes = True


class CreateBackgroundCheckIn(BaseModel):
    staff_id: uuid.UUID
    provider: Optional[str] = Field(default=None, max_length=50)
    check_type: str = Field(default="dbs", max_length=30)
    issued_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    badge_visible: bool = True
    reference_number: Optional[str] = Field(default=None, max_length=100)


class UpdateBackgroundCheckIn(BaseModel):
    provider: Optional[str] = Field(default=None, max_length=50)
    check_type: Optional[str] = Field(default=None, max_length=30)
    issued_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    badge_visible: Optional[bool] = None
    reference_number: Optional[str] = Field(default=None, max_length=100)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[BackgroundCheckOut])
async def list_background_checks(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    staff_id: Optional[uuid.UUID] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    try:
        org_id = _org_id(ctx)
        q = select(StaffBackgroundCheck).where(StaffBackgroundCheck.org_id == org_id)
        if staff_id:
            q = q.where(StaffBackgroundCheck.staff_id == staff_id)
        if status:
            q = q.where(StaffBackgroundCheck.status == status)
        q = q.order_by(StaffBackgroundCheck.created_at.desc()).limit(limit).offset(offset)
        rows = (await db.execute(q)).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_background_checks failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=BackgroundCheckOut, status_code=201)
async def create_background_check(
    body: CreateBackgroundCheckIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = StaffBackgroundCheck(
            org_id=org_id,
            staff_id=body.staff_id,
            provider=body.provider,
            check_type=body.check_type,
            issued_date=body.issued_date,
            expiry_date=body.expiry_date,
            badge_visible=body.badge_visible,
            reference_number=body.reference_number,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_background_check failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{check_id}", response_model=BackgroundCheckOut)
async def update_background_check(
    check_id: uuid.UUID,
    body: UpdateBackgroundCheckIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(StaffBackgroundCheck, check_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="Background check not found")
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(record, field, value)
        record.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_background_check failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{check_id}/clear", response_model=BackgroundCheckOut)
async def clear_background_check(
    check_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(StaffBackgroundCheck, check_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="Background check not found")
        record.status = "clear"
        record.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"clear_background_check failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{check_id}/flag", response_model=BackgroundCheckOut)
async def flag_background_check(
    check_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(StaffBackgroundCheck, check_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="Background check not found")
        record.status = "flagged"
        record.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"flag_background_check failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{check_id}", status_code=204)
async def delete_background_check(
    check_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(StaffBackgroundCheck, check_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="Background check not found")
        await db.delete(record)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_background_check failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/public/{staff_id}", response_model=list[PublicBackgroundCheckOut])
async def public_staff_badges(
    staff_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """PUBLIC endpoint — returns only badge_visible=true records for a staff member."""
    try:
        q = (
            select(StaffBackgroundCheck)
            .where(
                StaffBackgroundCheck.staff_id == staff_id,
                StaffBackgroundCheck.badge_visible.is_(True),
            )
            .order_by(StaffBackgroundCheck.issued_date.desc())
        )
        rows = (await db.execute(q)).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"public_staff_badges failed: {e}", extra={"staff_id": str(staff_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
