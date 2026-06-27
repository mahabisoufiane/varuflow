"""Important Dates router — Sprint 9: Personalization.

Endpoint map
------------
    GET   /api/important-dates              — list (filter by customer_id, upcoming_days)
    POST  /api/important-dates              — create
    PATCH /api/important-dates/{id}         — update
    DELETE /api/important-dates/{id}        — delete
"""
from __future__ import annotations

import logging
import uuid
import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from .customer_important_date import CustomerImportantDate
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/important-dates", tags=["important-dates"], dependencies=[Depends(require_module("hr"))])


class ImportantDateIn(BaseModel):
    customer_id: uuid.UUID
    label: str
    date: datetime.date
    send_greeting: bool = True
    send_discount: bool = False
    discount_pct: int | None = None


class ImportantDatePatch(BaseModel):
    label: str | None = None
    date: datetime.date | None = None
    send_greeting: bool | None = None
    send_discount: bool | None = None
    discount_pct: int | None = None
    last_triggered_year: int | None = None


class ImportantDateOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    label: str
    date: datetime.date
    send_greeting: bool
    send_discount: bool
    discount_pct: int | None
    last_triggered_year: int | None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[ImportantDateOut])
async def list_important_dates(
    customer_id: uuid.UUID | None = Query(None),
    upcoming_days: int | None = Query(None, ge=1, le=365),
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(CustomerImportantDate).where(CustomerImportantDate.org_id == org_id)
        if customer_id is not None:
            q = q.where(CustomerImportantDate.customer_id == customer_id)
        if upcoming_days is not None:
            # Filter records whose (month, day) falls within next N days from today
            upcoming_filter = text(
                """
                (
                    MAKE_DATE(
                        CASE
                            WHEN (EXTRACT(MONTH FROM date)::int, EXTRACT(DAY FROM date)::int)
                                 >= (EXTRACT(MONTH FROM CURRENT_DATE)::int, EXTRACT(DAY FROM CURRENT_DATE)::int)
                            THEN EXTRACT(YEAR FROM CURRENT_DATE)::int
                            ELSE EXTRACT(YEAR FROM CURRENT_DATE)::int + 1
                        END,
                        EXTRACT(MONTH FROM date)::int,
                        EXTRACT(DAY FROM date)::int
                    )
                ) BETWEEN CURRENT_DATE AND (CURRENT_DATE + :days * INTERVAL '1 day')
                """
            ).bindparams(days=upcoming_days)
            q = q.where(upcoming_filter)
        q = q.order_by(CustomerImportantDate.date)
        result = await db.execute(q)
        return [ImportantDateOut.model_validate(r) for r in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_important_dates failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=ImportantDateOut, status_code=201)
async def create_important_date(
    body: ImportantDateIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        row = CustomerImportantDate(
            org_id=org_id,
            customer_id=body.customer_id,
            label=body.label,
            date=body.date,
            send_greeting=body.send_greeting,
            send_discount=body.send_discount,
            discount_pct=body.discount_pct,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return ImportantDateOut.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_important_date failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{date_id}", response_model=ImportantDateOut)
async def update_important_date(
    date_id: uuid.UUID,
    body: ImportantDatePatch,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        result = await db.execute(
            select(CustomerImportantDate).where(
                CustomerImportantDate.id == date_id,
                CustomerImportantDate.org_id == org_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Important date not found")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        row.updated_at = datetime.datetime.now(datetime.timezone.utc)
        await db.commit()
        await db.refresh(row)
        return ImportantDateOut.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_important_date failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{date_id}", status_code=204)
async def delete_important_date(
    date_id: uuid.UUID,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        result = await db.execute(
            select(CustomerImportantDate).where(
                CustomerImportantDate.id == date_id,
                CustomerImportantDate.org_id == org_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Important date not found")
        await db.delete(row)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_important_date failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")
