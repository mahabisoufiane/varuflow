"""Portfolio photos router (Sprint 11) — prefix /api/portfolio."""
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
from app.models.staff_portfolio_photo import StaffPortfolioPhoto

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class PortfolioPhotoOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    staff_id: Optional[uuid.UUID]
    service_id: Optional[uuid.UUID]
    title: Optional[str]
    description: Optional[str]
    photo_url: str
    is_featured: bool
    sort_order: int
    created_at: datetime

    class Config:
        from_attributes = True


class CreatePhotoIn(BaseModel):
    staff_id: Optional[uuid.UUID] = None
    service_id: Optional[uuid.UUID] = None
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    photo_url: str = Field(..., max_length=500)
    is_featured: bool = False
    sort_order: int = 0


class UpdatePhotoIn(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    is_featured: Optional[bool] = None
    sort_order: Optional[int] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/public/{staff_id}", response_model=list[PortfolioPhotoOut])
async def list_public_photos(
    staff_id: uuid.UUID,
    org_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """PUBLIC — no auth required. Returns all photos for a staff member."""
    try:
        rows = (
            await db.execute(
                select(StaffPortfolioPhoto)
                .where(
                    StaffPortfolioPhoto.org_id == org_id,
                    StaffPortfolioPhoto.staff_id == staff_id,
                )
                .order_by(StaffPortfolioPhoto.sort_order.asc(), StaffPortfolioPhoto.created_at.desc())
            )
        ).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_public_photos failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=list[PortfolioPhotoOut])
async def list_photos(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    staff_id: Optional[uuid.UUID] = Query(default=None),
    service_id: Optional[uuid.UUID] = Query(default=None),
    featured_only: bool = Query(default=False),
):
    try:
        org_id = _org_id(ctx)
        q = select(StaffPortfolioPhoto).where(StaffPortfolioPhoto.org_id == org_id)
        if staff_id:
            q = q.where(StaffPortfolioPhoto.staff_id == staff_id)
        if service_id:
            q = q.where(StaffPortfolioPhoto.service_id == service_id)
        if featured_only:
            q = q.where(StaffPortfolioPhoto.is_featured.is_(True))
        q = q.order_by(StaffPortfolioPhoto.sort_order.asc(), StaffPortfolioPhoto.created_at.desc())
        rows = (await db.execute(q)).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_photos failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=PortfolioPhotoOut, status_code=201)
async def create_photo(
    body: CreatePhotoIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        photo = StaffPortfolioPhoto(
            org_id=org_id,
            staff_id=body.staff_id,
            service_id=body.service_id,
            title=body.title,
            description=body.description,
            photo_url=body.photo_url,
            is_featured=body.is_featured,
            sort_order=body.sort_order,
        )
        db.add(photo)
        await db.commit()
        await db.refresh(photo)
        return photo
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_photo failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{photo_id}", response_model=PortfolioPhotoOut)
async def update_photo(
    photo_id: uuid.UUID,
    body: UpdatePhotoIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        photo = await db.get(StaffPortfolioPhoto, photo_id)
        if not photo or photo.org_id != org_id:
            raise HTTPException(status_code=404, detail="Photo not found")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(photo, field, value)
        await db.commit()
        await db.refresh(photo)
        return photo
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_photo failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{photo_id}/feature", response_model=PortfolioPhotoOut)
async def feature_photo(
    photo_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        photo = await db.get(StaffPortfolioPhoto, photo_id)
        if not photo or photo.org_id != org_id:
            raise HTTPException(status_code=404, detail="Photo not found")
        photo.is_featured = True
        await db.commit()
        await db.refresh(photo)
        return photo
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"feature_photo failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{photo_id}", status_code=204)
async def delete_photo(
    photo_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        photo = await db.get(StaffPortfolioPhoto, photo_id)
        if not photo or photo.org_id != org_id:
            raise HTTPException(status_code=404, detail="Photo not found")
        await db.delete(photo)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_photo failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
