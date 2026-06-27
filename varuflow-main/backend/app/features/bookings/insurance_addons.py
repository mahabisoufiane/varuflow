"""Insurance add-ons router (Sprint 12) — prefix /api/insurance."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.features.bookings.service_insurance_addon import BookingInsurancePurchase, ServiceInsuranceAddon
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/insurance", tags=["insurance-addons"], dependencies=[Depends(require_module("finance"))])


# ── Schemas ──────────────────────────────────────────────────────────────────

class InsuranceAddonOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    service_id: Optional[uuid.UUID]
    name: str
    description: Optional[str]
    price: Decimal
    coverage_description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CreateInsuranceAddonIn(BaseModel):
    service_id: Optional[uuid.UUID] = None
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    price: Decimal = Field(default=Decimal("0"))
    coverage_description: Optional[str] = None
    is_active: bool = True


class UpdateInsuranceAddonIn(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    price: Optional[Decimal] = None
    coverage_description: Optional[str] = None
    is_active: Optional[bool] = None


class InsurancePurchaseOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    booking_id: Optional[uuid.UUID]
    customer_id: uuid.UUID
    addon_id: Optional[uuid.UUID]
    amount_paid: Decimal
    policy_ref: Optional[str]
    status: str
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class CreateInsurancePurchaseIn(BaseModel):
    booking_id: Optional[uuid.UUID] = None
    customer_id: uuid.UUID
    addon_id: Optional[uuid.UUID] = None
    amount_paid: Decimal
    policy_ref: Optional[str] = Field(default=None, max_length=100)
    expires_at: Optional[datetime] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Add-on endpoints ──────────────────────────────────────────────────────────

@router.get("/addons", response_model=list[InsuranceAddonOut])
async def list_insurance_addons(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    service_id: Optional[uuid.UUID] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    try:
        org_id = _org_id(ctx)
        q = select(ServiceInsuranceAddon).where(ServiceInsuranceAddon.org_id == org_id)
        if service_id:
            q = q.where(ServiceInsuranceAddon.service_id == service_id)
        q = q.order_by(ServiceInsuranceAddon.created_at.desc()).limit(limit).offset(offset)
        rows = (await db.execute(q)).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_insurance_addons failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/addons", response_model=InsuranceAddonOut, status_code=201)
async def create_insurance_addon(
    body: CreateInsuranceAddonIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = ServiceInsuranceAddon(
            org_id=org_id,
            service_id=body.service_id,
            name=body.name,
            description=body.description,
            price=body.price,
            coverage_description=body.coverage_description,
            is_active=body.is_active,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_insurance_addon failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/addons/{addon_id}", response_model=InsuranceAddonOut)
async def update_insurance_addon(
    addon_id: uuid.UUID,
    body: UpdateInsuranceAddonIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(ServiceInsuranceAddon, addon_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="Add-on not found")
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(record, field, value)
        record.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_insurance_addon failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/addons/{addon_id}", status_code=204)
async def delete_insurance_addon(
    addon_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(ServiceInsuranceAddon, addon_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="Add-on not found")
        await db.delete(record)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_insurance_addon failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Purchase endpoints ────────────────────────────────────────────────────────

@router.get("/purchases", response_model=list[InsurancePurchaseOut])
async def list_insurance_purchases(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    customer_id: Optional[uuid.UUID] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    try:
        org_id = _org_id(ctx)
        q = select(BookingInsurancePurchase).where(BookingInsurancePurchase.org_id == org_id)
        if customer_id:
            q = q.where(BookingInsurancePurchase.customer_id == customer_id)
        if status:
            q = q.where(BookingInsurancePurchase.status == status)
        q = q.order_by(BookingInsurancePurchase.created_at.desc()).limit(limit).offset(offset)
        rows = (await db.execute(q)).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_insurance_purchases failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/purchases", response_model=InsurancePurchaseOut, status_code=201)
async def create_insurance_purchase(
    body: CreateInsurancePurchaseIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = BookingInsurancePurchase(
            org_id=org_id,
            booking_id=body.booking_id,
            customer_id=body.customer_id,
            addon_id=body.addon_id,
            amount_paid=body.amount_paid,
            policy_ref=body.policy_ref,
            expires_at=body.expires_at,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_insurance_purchase failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/purchases/{purchase_id}/claim", response_model=InsurancePurchaseOut)
async def claim_insurance_purchase(
    purchase_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(BookingInsurancePurchase, purchase_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="Purchase not found")
        record.status = "claimed"
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"claim_insurance_purchase failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/purchases/{purchase_id}/refund", response_model=InsurancePurchaseOut)
async def refund_insurance_purchase(
    purchase_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(BookingInsurancePurchase, purchase_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="Purchase not found")
        record.status = "refunded"
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"refund_insurance_purchase failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
