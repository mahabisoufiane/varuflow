"""Birthday Vouchers router — Sprint 9: Loyalty & Rewards.

Endpoint map
------------
    GET  /api/birthday-vouchers             — list (filter by customer_id, year)
    POST /api/birthday-vouchers             — generate voucher
    POST /api/birthday-vouchers/{id}/redeem — redeem voucher
    DELETE /api/birthday-vouchers/{id}      — delete voucher
"""
from __future__ import annotations

import logging
import secrets
import uuid
import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.birthday_voucher import BirthdayVoucher

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/birthday-vouchers", tags=["birthday-vouchers"])


class VoucherIn(BaseModel):
    customer_id: uuid.UUID
    discount_type: str = "pct"
    discount_value: float
    valid_from: datetime.date
    valid_until: datetime.date
    generated_for_year: int


class VoucherOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    voucher_code: str
    discount_type: str
    discount_value: float
    valid_from: datetime.date
    valid_until: datetime.date
    is_redeemed: bool
    redeemed_at: datetime.datetime | None
    generated_for_year: int
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[VoucherOut])
async def list_birthday_vouchers(
    customer_id: uuid.UUID | None = Query(None),
    year: int | None = Query(None),
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(BirthdayVoucher).where(BirthdayVoucher.org_id == org_id)
        if customer_id is not None:
            q = q.where(BirthdayVoucher.customer_id == customer_id)
        if year is not None:
            q = q.where(BirthdayVoucher.generated_for_year == year)
        q = q.order_by(BirthdayVoucher.created_at.desc())
        result = await db.execute(q)
        return [VoucherOut.model_validate(r) for r in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_birthday_vouchers failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=VoucherOut, status_code=201)
async def create_birthday_voucher(
    body: VoucherIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        voucher_code = secrets.token_hex(5).upper()
        row = BirthdayVoucher(
            org_id=org_id,
            customer_id=body.customer_id,
            voucher_code=voucher_code,
            discount_type=body.discount_type,
            discount_value=body.discount_value,
            valid_from=body.valid_from,
            valid_until=body.valid_until,
            generated_for_year=body.generated_for_year,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return VoucherOut.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_birthday_voucher failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{voucher_id}/redeem", response_model=VoucherOut)
async def redeem_birthday_voucher(
    voucher_id: uuid.UUID,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        result = await db.execute(
            select(BirthdayVoucher).where(
                BirthdayVoucher.id == voucher_id,
                BirthdayVoucher.org_id == org_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Birthday voucher not found")
        if row.is_redeemed:
            raise HTTPException(status_code=422, detail="Voucher already redeemed")
        row.is_redeemed = True
        row.redeemed_at = datetime.datetime.utcnow()
        await db.commit()
        await db.refresh(row)
        return VoucherOut.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"redeem_birthday_voucher failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{voucher_id}", status_code=204)
async def delete_birthday_voucher(
    voucher_id: uuid.UUID,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        result = await db.execute(
            select(BirthdayVoucher).where(
                BirthdayVoucher.id == voucher_id,
                BirthdayVoucher.org_id == org_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Birthday voucher not found")
        await db.delete(row)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_birthday_voucher failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")
