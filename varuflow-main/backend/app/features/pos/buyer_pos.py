"""Buyer-submitted purchase orders — Sprint 10.

Endpoints under ``/api/buyer-pos``:

    GET    ""                               list POs (filter customer_id, status)
    POST   ""                               create PO with line_items
    GET    /{id}                            detail with line items
    PATCH  /{id}                            update (draft only)
    POST   /{id}/submit                     set status=submitted
    POST   /{id}/confirm                    staff confirms PO
    POST   /{id}/reject                     set status=rejected
    POST   /{id}/fulfill                    set status=fulfilled
    GET    /reorder/{customer_id}           last confirmed/fulfilled PO line items
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.features.purchases.buyer_purchase_order import BuyerPoLineItem, BuyerPurchaseOrder

router = APIRouter(prefix="/api/buyer-pos", tags=["buyer-pos"], dependencies=[Depends(require_module("pos"))])
logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────────────

class LineItemIn(BaseModel):
    product_id: uuid.UUID | None = None
    description: str
    quantity: Decimal = Decimal("1")
    unit_price: Decimal | None = None
    sort_order: int = 0


class BuyerPoCreate(BaseModel):
    customer_id: uuid.UUID
    buyer_po_number: str
    buyer_org_name: str | None = None
    notes: str | None = None
    requested_delivery_date: date | None = None
    line_items: list[LineItemIn] = []


class BuyerPoUpdate(BaseModel):
    buyer_po_number: str | None = None
    buyer_org_name: str | None = None
    notes: str | None = None
    requested_delivery_date: date | None = None


class LineItemOut(BaseModel):
    id: uuid.UUID
    buyer_po_id: uuid.UUID
    product_id: uuid.UUID | None
    description: str
    quantity: Decimal
    unit_price: Decimal | None
    sort_order: int
    created_at: datetime


class BuyerPoOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    buyer_po_number: str
    buyer_org_name: str | None
    status: str
    notes: str | None
    requested_delivery_date: date | None
    confirmed_by_staff_user_id: uuid.UUID | None
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    line_items: list[LineItemOut] = []


def _line_to_out(li: BuyerPoLineItem) -> LineItemOut:
    return LineItemOut(
        id=li.id,
        buyer_po_id=li.buyer_po_id,
        product_id=li.product_id,
        description=li.description,
        quantity=li.quantity,
        unit_price=li.unit_price,
        sort_order=li.sort_order,
        created_at=li.created_at,
    )


def _to_out(row: BuyerPurchaseOrder, line_items: list[BuyerPoLineItem] | None = None) -> BuyerPoOut:
    return BuyerPoOut(
        id=row.id,
        org_id=row.org_id,
        customer_id=row.customer_id,
        buyer_po_number=row.buyer_po_number,
        buyer_org_name=row.buyer_org_name,
        status=row.status,
        notes=row.notes,
        requested_delivery_date=row.requested_delivery_date,
        confirmed_by_staff_user_id=row.confirmed_by_staff_user_id,
        confirmed_at=row.confirmed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        line_items=[_line_to_out(li) for li in (line_items or [])],
    )


async def _load(db: AsyncSession, *, po_id: uuid.UUID, org_id: uuid.UUID) -> BuyerPurchaseOrder:
    row = await db.get(BuyerPurchaseOrder, po_id)
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return row


async def _get_line_items(db: AsyncSession, po_id: uuid.UUID) -> list[BuyerPoLineItem]:
    stmt = select(BuyerPoLineItem).where(BuyerPoLineItem.buyer_po_id == po_id).order_by(BuyerPoLineItem.sort_order)
    return list((await db.scalars(stmt)).all())


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/reorder/{customer_id}", response_model=list[LineItemOut])
async def get_reorder_items(
    customer_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return line items from the most recent confirmed/fulfilled PO for pre-filling a new PO."""
    try:
        _user, member = ctx
        stmt = (
            select(BuyerPurchaseOrder)
            .where(
                BuyerPurchaseOrder.org_id == member.org_id,
                BuyerPurchaseOrder.customer_id == customer_id,
                BuyerPurchaseOrder.status.in_(["confirmed", "fulfilled"]),
            )
            .order_by(BuyerPurchaseOrder.created_at.desc())
            .limit(1)
        )
        po = (await db.scalars(stmt)).first()
        if po is None:
            return []
        return [_line_to_out(li) for li in await _get_line_items(db, po.id)]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_reorder_items failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=list[BuyerPoOut])
async def list_buyer_pos(
    customer_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        stmt = select(BuyerPurchaseOrder).where(BuyerPurchaseOrder.org_id == member.org_id)
        if customer_id is not None:
            stmt = stmt.where(BuyerPurchaseOrder.customer_id == customer_id)
        if status is not None:
            stmt = stmt.where(BuyerPurchaseOrder.status == status)
        stmt = stmt.order_by(BuyerPurchaseOrder.created_at.desc()).limit(limit).offset(offset)
        rows = (await db.scalars(stmt)).all()
        return [_to_out(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_buyer_pos failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=BuyerPoOut, status_code=201)
async def create_buyer_po(
    body: BuyerPoCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        po = BuyerPurchaseOrder(
            org_id=member.org_id,
            customer_id=body.customer_id,
            buyer_po_number=body.buyer_po_number,
            buyer_org_name=body.buyer_org_name,
            notes=body.notes,
            requested_delivery_date=body.requested_delivery_date,
            status="draft",
        )
        db.add(po)
        await db.flush()
        line_items = []
        for li in body.line_items:
            item = BuyerPoLineItem(
                buyer_po_id=po.id,
                product_id=li.product_id,
                description=li.description,
                quantity=li.quantity,
                unit_price=li.unit_price,
                sort_order=li.sort_order,
            )
            db.add(item)
            line_items.append(item)
        await db.commit()
        await db.refresh(po)
        for li in line_items:
            await db.refresh(li)
        return _to_out(po, line_items)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_buyer_po failed: {str(e)}", extra={"org_id": str(member.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{po_id}", response_model=BuyerPoOut)
async def get_buyer_po(
    po_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        po = await _load(db, po_id=po_id, org_id=member.org_id)
        line_items = await _get_line_items(db, po.id)
        return _to_out(po, line_items)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_buyer_po failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{po_id}", response_model=BuyerPoOut)
async def update_buyer_po(
    po_id: uuid.UUID,
    body: BuyerPoUpdate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        po = await _load(db, po_id=po_id, org_id=member.org_id)
        if po.status != "draft":
            raise HTTPException(status_code=400, detail="Only draft POs can be updated")
        for field, val in body.model_dump(exclude_unset=True).items():
            setattr(po, field, val)
        await db.commit()
        await db.refresh(po)
        line_items = await _get_line_items(db, po.id)
        return _to_out(po, line_items)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_buyer_po failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{po_id}/submit", response_model=BuyerPoOut)
async def submit_buyer_po(
    po_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        po = await _load(db, po_id=po_id, org_id=member.org_id)
        po.status = "submitted"
        await db.commit()
        await db.refresh(po)
        line_items = await _get_line_items(db, po.id)
        return _to_out(po, line_items)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"submit_buyer_po failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{po_id}/confirm", response_model=BuyerPoOut)
async def confirm_buyer_po(
    po_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        user, member = ctx
        po = await _load(db, po_id=po_id, org_id=member.org_id)
        po.status = "confirmed"
        po.confirmed_by_staff_user_id = uuid.UUID(user["user_id"])
        po.confirmed_at = datetime.now(tz=timezone.utc)
        await db.commit()
        await db.refresh(po)
        line_items = await _get_line_items(db, po.id)
        return _to_out(po, line_items)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"confirm_buyer_po failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{po_id}/reject", response_model=BuyerPoOut)
async def reject_buyer_po(
    po_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        po = await _load(db, po_id=po_id, org_id=member.org_id)
        po.status = "rejected"
        await db.commit()
        await db.refresh(po)
        line_items = await _get_line_items(db, po.id)
        return _to_out(po, line_items)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"reject_buyer_po failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{po_id}/fulfill", response_model=BuyerPoOut)
async def fulfill_buyer_po(
    po_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        po = await _load(db, po_id=po_id, org_id=member.org_id)
        po.status = "fulfilled"
        await db.commit()
        await db.refresh(po)
        line_items = await _get_line_items(db, po.id)
        return _to_out(po, line_items)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"fulfill_buyer_po failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
