"""Customer address book — Sprint 10.

Endpoints under ``/api/addresses``:

    GET    ""                      list addresses (filter by customer_id)
    POST   ""                      create address
    PATCH  /{id}                   update fields
    POST   /{id}/set-default       mark as default (clears others for same customer)
    DELETE /{id}                   remove address
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.customer_address import CustomerAddress

router = APIRouter(prefix="/api/addresses", tags=["addresses"])
logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────────────

class AddressCreate(BaseModel):
    customer_id: uuid.UUID
    label: str = "home"
    line1: str
    line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str = "SE"
    is_default: bool = False


class AddressUpdate(BaseModel):
    label: str | None = None
    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    is_default: bool | None = None


class AddressOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    label: str
    line1: str
    line2: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    country: str
    is_default: bool
    created_at: datetime
    updated_at: datetime


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_out(row: CustomerAddress) -> AddressOut:
    return AddressOut(
        id=row.id,
        org_id=row.org_id,
        customer_id=row.customer_id,
        label=row.label,
        line1=row.line1,
        line2=row.line2,
        city=row.city,
        state=row.state,
        postal_code=row.postal_code,
        country=row.country,
        is_default=row.is_default,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _load(db: AsyncSession, *, addr_id: uuid.UUID, org_id: uuid.UUID) -> CustomerAddress:
    row = await db.get(CustomerAddress, addr_id)
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Address not found")
    return row


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[AddressOut])
async def list_addresses(
    customer_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        stmt = select(CustomerAddress).where(CustomerAddress.org_id == member.org_id)
        if customer_id is not None:
            stmt = stmt.where(CustomerAddress.customer_id == customer_id)
        stmt = stmt.order_by(CustomerAddress.is_default.desc(), CustomerAddress.label).limit(limit).offset(offset)
        rows = (await db.scalars(stmt)).all()
        return [_to_out(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_addresses failed: {str(e)}", extra={"org_id": str(ctx[1].org_id) if ctx else None})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
async def create_address(
    body: AddressCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        if body.is_default:
            await db.execute(
                update(CustomerAddress)
                .where(CustomerAddress.org_id == member.org_id, CustomerAddress.customer_id == body.customer_id)
                .values(is_default=False)
            )
        row = CustomerAddress(
            org_id=member.org_id,
            customer_id=body.customer_id,
            label=body.label,
            line1=body.line1,
            line2=body.line2,
            city=body.city,
            state=body.state,
            postal_code=body.postal_code,
            country=body.country,
            is_default=body.is_default,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _to_out(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_address failed: {str(e)}", extra={"org_id": str(member.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{addr_id}", response_model=AddressOut)
async def update_address(
    addr_id: uuid.UUID,
    body: AddressUpdate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        row = await _load(db, addr_id=addr_id, org_id=member.org_id)
        for field, val in body.model_dump(exclude_unset=True).items():
            setattr(row, field, val)
        await db.commit()
        await db.refresh(row)
        return _to_out(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_address failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{addr_id}/set-default", response_model=AddressOut)
async def set_default_address(
    addr_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        row = await _load(db, addr_id=addr_id, org_id=member.org_id)
        # Clear all defaults for this customer first
        await db.execute(
            update(CustomerAddress)
            .where(CustomerAddress.org_id == member.org_id, CustomerAddress.customer_id == row.customer_id)
            .values(is_default=False)
        )
        row.is_default = True
        await db.commit()
        await db.refresh(row)
        return _to_out(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"set_default_address failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{addr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(
    addr_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        row = await _load(db, addr_id=addr_id, org_id=member.org_id)
        await db.delete(row)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_address failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
