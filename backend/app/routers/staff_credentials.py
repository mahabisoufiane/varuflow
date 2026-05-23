"""Staff credentials router (Sprint 11) — prefix /api/staff-credentials."""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.staff_credential import StaffCredential

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/staff-credentials", tags=["staff-credentials"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class StaffCredentialOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    staff_id: uuid.UUID
    credential_type: str
    title: str
    issuing_body: Optional[str]
    issued_date: Optional[date]
    expiry_date: Optional[date]
    is_visible_to_customers: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CreateCredentialIn(BaseModel):
    staff_id: uuid.UUID
    credential_type: str = Field(default="certification", max_length=30)
    title: str = Field(..., max_length=200)
    issuing_body: Optional[str] = Field(default=None, max_length=200)
    issued_date: Optional[date] = None
    expiry_date: Optional[date] = None
    is_visible_to_customers: bool = True


class UpdateCredentialIn(BaseModel):
    credential_type: Optional[str] = Field(default=None, max_length=30)
    title: Optional[str] = Field(default=None, max_length=200)
    issuing_body: Optional[str] = Field(default=None, max_length=200)
    issued_date: Optional[date] = None
    expiry_date: Optional[date] = None
    is_visible_to_customers: Optional[bool] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/public/{staff_id}", response_model=list[StaffCredentialOut])
async def list_public_credentials(
    staff_id: uuid.UUID,
    org_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """PUBLIC — no auth required. Returns only customer-visible credentials."""
    try:
        rows = (
            await db.execute(
                select(StaffCredential).where(
                    StaffCredential.org_id == org_id,
                    StaffCredential.staff_id == staff_id,
                    StaffCredential.is_visible_to_customers.is_(True),
                )
            )
        ).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_public_credentials failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=list[StaffCredentialOut])
async def list_credentials(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    staff_id: Optional[uuid.UUID] = Query(default=None),
    is_visible: Optional[bool] = Query(default=None),
):
    try:
        org_id = _org_id(ctx)
        q = select(StaffCredential).where(StaffCredential.org_id == org_id)
        if staff_id:
            q = q.where(StaffCredential.staff_id == staff_id)
        if is_visible is not None:
            q = q.where(StaffCredential.is_visible_to_customers == is_visible)
        rows = (await db.execute(q)).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_credentials failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=StaffCredentialOut, status_code=201)
async def create_credential(
    body: CreateCredentialIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        cred = StaffCredential(
            org_id=org_id,
            staff_id=body.staff_id,
            credential_type=body.credential_type,
            title=body.title,
            issuing_body=body.issuing_body,
            issued_date=body.issued_date,
            expiry_date=body.expiry_date,
            is_visible_to_customers=body.is_visible_to_customers,
        )
        db.add(cred)
        await db.commit()
        await db.refresh(cred)
        return cred
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_credential failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{credential_id}", response_model=StaffCredentialOut)
async def update_credential(
    credential_id: uuid.UUID,
    body: UpdateCredentialIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        cred = await db.get(StaffCredential, credential_id)
        if not cred or cred.org_id != org_id:
            raise HTTPException(status_code=404, detail="Credential not found")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(cred, field, value)
        cred.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(cred)
        return cred
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_credential failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{credential_id}", status_code=204)
async def delete_credential(
    credential_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        cred = await db.get(StaffCredential, credential_id)
        if not cred or cred.org_id != org_id:
            raise HTTPException(status_code=404, detail="Credential not found")
        await db.delete(cred)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_credential failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
