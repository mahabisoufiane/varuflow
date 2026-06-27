"""Saved Payment Methods router — Sprint 9: Personalization.

Endpoint map
------------
    GET  /api/payment-methods               — list for customer
    POST /api/payment-methods               — create
    PATCH /api/payment-methods/{id}         — update nickname / is_default
    POST /api/payment-methods/{id}/set-default — set as default
    DELETE /api/payment-methods/{id}        — soft delete (is_active=false)
"""
from __future__ import annotations

import logging
import uuid
import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.saved_payment_method import SavedPaymentMethod

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payment-methods", tags=["saved-payment-methods"])


class PaymentMethodIn(BaseModel):
    customer_id: uuid.UUID
    provider: str = "stripe"
    card_last4: str | None = None
    card_brand: str | None = None
    card_exp_month: int | None = None
    card_exp_year: int | None = None
    provider_payment_method_id: str | None = None
    is_default: bool = False
    nickname: str | None = None


class PaymentMethodPatch(BaseModel):
    nickname: str | None = None
    is_default: bool | None = None


class PaymentMethodOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    provider: str
    card_last4: str | None
    card_brand: str | None
    card_exp_month: int | None
    card_exp_year: int | None
    provider_payment_method_id: str | None
    is_default: bool
    nickname: str | None
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[PaymentMethodOut])
async def list_payment_methods(
    customer_id: uuid.UUID = Query(...),
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        result = await db.execute(
            select(SavedPaymentMethod).where(
                SavedPaymentMethod.org_id == org_id,
                SavedPaymentMethod.customer_id == customer_id,
                SavedPaymentMethod.is_active == True,
            ).order_by(SavedPaymentMethod.is_default.desc(), SavedPaymentMethod.created_at)
        )
        return [PaymentMethodOut.model_validate(r) for r in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_payment_methods failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=PaymentMethodOut, status_code=201)
async def create_payment_method(
    body: PaymentMethodIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        # If this is default, unset others
        if body.is_default:
            await db.execute(
                update(SavedPaymentMethod)
                .where(
                    SavedPaymentMethod.org_id == org_id,
                    SavedPaymentMethod.customer_id == body.customer_id,
                )
                .values(is_default=False)
            )
        row = SavedPaymentMethod(
            org_id=org_id,
            customer_id=body.customer_id,
            provider=body.provider,
            card_last4=body.card_last4,
            card_brand=body.card_brand,
            card_exp_month=body.card_exp_month,
            card_exp_year=body.card_exp_year,
            provider_payment_method_id=body.provider_payment_method_id,
            is_default=body.is_default,
            nickname=body.nickname,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return PaymentMethodOut.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_payment_method failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


async def _get_method(method_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession) -> SavedPaymentMethod:
    result = await db.execute(
        select(SavedPaymentMethod).where(
            SavedPaymentMethod.id == method_id,
            SavedPaymentMethod.org_id == org_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Payment method not found")
    return row


@router.patch("/{method_id}", response_model=PaymentMethodOut)
async def update_payment_method(
    method_id: uuid.UUID,
    body: PaymentMethodPatch,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        row = await _get_method(method_id, org_id, db)
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        row.updated_at = datetime.datetime.utcnow()
        await db.commit()
        await db.refresh(row)
        return PaymentMethodOut.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_payment_method failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{method_id}/set-default", response_model=PaymentMethodOut)
async def set_default_payment_method(
    method_id: uuid.UUID,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        row = await _get_method(method_id, org_id, db)
        # Unset all others for the same customer
        await db.execute(
            update(SavedPaymentMethod)
            .where(
                SavedPaymentMethod.org_id == org_id,
                SavedPaymentMethod.customer_id == row.customer_id,
            )
            .values(is_default=False)
        )
        row.is_default = True
        row.updated_at = datetime.datetime.utcnow()
        await db.commit()
        await db.refresh(row)
        return PaymentMethodOut.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"set_default_payment_method failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{method_id}", status_code=204)
async def delete_payment_method(
    method_id: uuid.UUID,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        row = await _get_method(method_id, org_id, db)
        row.is_active = False
        row.updated_at = datetime.datetime.utcnow()
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_payment_method failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")
