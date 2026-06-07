"""Return pickup requests router (Sprint 11) — prefix /api/return-pickups."""
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
from app.models.return_pickup import ReturnPickupRequest
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/return-pickups", tags=["return-pickups"], dependencies=[Depends(require_module("invoicing"))])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ReturnPickupOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    invoice_id: Optional[uuid.UUID]
    return_request_id: Optional[uuid.UUID]
    courier_provider: Optional[str]
    pickup_address_line1: str
    pickup_address_city: str
    pickup_postal_code: Optional[str]
    pickup_country: str
    preferred_date: date
    preferred_time_slot: str
    status: str
    courier_tracking_number: Optional[str]
    courier_booked_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CreatePickupIn(BaseModel):
    customer_id: uuid.UUID
    invoice_id: Optional[uuid.UUID] = None
    return_request_id: Optional[uuid.UUID] = None
    courier_provider: Optional[str] = Field(default=None, max_length=50)
    pickup_address_line1: str = Field(..., max_length=200)
    pickup_address_city: str = Field(..., max_length=100)
    pickup_postal_code: Optional[str] = Field(default=None, max_length=20)
    pickup_country: str = Field(default="SE", max_length=2)
    preferred_date: date
    preferred_time_slot: str = Field(default="morning", max_length=20)


class UpdatePickupIn(BaseModel):
    preferred_date: Optional[date] = None
    preferred_time_slot: Optional[str] = Field(default=None, max_length=20)


class SchedulePickupIn(BaseModel):
    courier_provider: str = Field(..., max_length=50)
    courier_tracking_number: str = Field(..., max_length=100)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ReturnPickupOut])
async def list_return_pickups(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    customer_id: Optional[uuid.UUID] = Query(default=None),
    status: Optional[str] = Query(default=None),
):
    try:
        org_id = _org_id(ctx)
        q = select(ReturnPickupRequest).where(ReturnPickupRequest.org_id == org_id)
        if customer_id:
            q = q.where(ReturnPickupRequest.customer_id == customer_id)
        if status:
            q = q.where(ReturnPickupRequest.status == status)
        q = q.order_by(ReturnPickupRequest.created_at.desc())
        rows = (await db.execute(q)).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_return_pickups failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=ReturnPickupOut, status_code=201)
async def create_return_pickup(
    body: CreatePickupIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        pickup = ReturnPickupRequest(
            org_id=org_id,
            customer_id=body.customer_id,
            invoice_id=body.invoice_id,
            return_request_id=body.return_request_id,
            courier_provider=body.courier_provider,
            pickup_address_line1=body.pickup_address_line1,
            pickup_address_city=body.pickup_address_city,
            pickup_postal_code=body.pickup_postal_code,
            pickup_country=body.pickup_country,
            preferred_date=body.preferred_date,
            preferred_time_slot=body.preferred_time_slot,
        )
        db.add(pickup)
        await db.commit()
        await db.refresh(pickup)
        return pickup
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_return_pickup failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{pickup_id}", response_model=ReturnPickupOut)
async def update_return_pickup(
    pickup_id: uuid.UUID,
    body: UpdatePickupIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        pickup = await db.get(ReturnPickupRequest, pickup_id)
        if not pickup or pickup.org_id != org_id:
            raise HTTPException(status_code=404, detail="Pickup request not found")
        if pickup.status != "pending":
            raise HTTPException(status_code=422, detail="Only pending pickups can be updated")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(pickup, field, value)
        pickup.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(pickup)
        return pickup
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_return_pickup failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{pickup_id}/schedule", response_model=ReturnPickupOut)
async def schedule_pickup(
    pickup_id: uuid.UUID,
    body: SchedulePickupIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        pickup = await db.get(ReturnPickupRequest, pickup_id)
        if not pickup or pickup.org_id != org_id:
            raise HTTPException(status_code=404, detail="Pickup request not found")
        pickup.courier_provider = body.courier_provider
        pickup.courier_tracking_number = body.courier_tracking_number
        pickup.status = "scheduled"
        pickup.courier_booked_at = datetime.now(timezone.utc)
        pickup.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(pickup)
        return pickup
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"schedule_pickup failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{pickup_id}/collect", response_model=ReturnPickupOut)
async def collect_pickup(
    pickup_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        pickup = await db.get(ReturnPickupRequest, pickup_id)
        if not pickup or pickup.org_id != org_id:
            raise HTTPException(status_code=404, detail="Pickup request not found")
        pickup.status = "collected"
        pickup.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(pickup)
        return pickup
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"collect_pickup failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{pickup_id}/fail", response_model=ReturnPickupOut)
async def fail_pickup(
    pickup_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        pickup = await db.get(ReturnPickupRequest, pickup_id)
        if not pickup or pickup.org_id != org_id:
            raise HTTPException(status_code=404, detail="Pickup request not found")
        pickup.status = "failed"
        pickup.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(pickup)
        return pickup
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"fail_pickup failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{pickup_id}", status_code=204)
async def delete_return_pickup(
    pickup_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        pickup = await db.get(ReturnPickupRequest, pickup_id)
        if not pickup or pickup.org_id != org_id:
            raise HTTPException(status_code=404, detail="Pickup request not found")
        await db.delete(pickup)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_return_pickup failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
