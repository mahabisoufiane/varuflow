"""POS quick-sale buttons router (Item 65).

Endpoints (all under ``/api/pos/quick-buttons``):

    GET    ""              list buttons ordered by position
    POST   ""              append a new button (capacity-checked)
    PATCH  /{button_id}    edit label / color / quantity
    DELETE /{button_id}    remove a button (positions stay stable)
    POST   /reorder        replace the full ordering in one call

Reorder uses a two-phase UPDATE: positions are first shifted out of
the unique-constraint space (into negatives) and then re-numbered
in the target order. Without this, ``(org_id, position)`` uniqueness
would trip on any swap.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.inventory import Product
from app.models.pos_quick_button import PosQuickButton
from app.services import pos_quick_button as svc
from app.services.audit import log_action

router = APIRouter(prefix="/api/pos/quick-buttons", tags=["pos-quick-buttons"], dependencies=[Depends(require_module("pos"))])

log = logging.getLogger(__name__)


class ButtonCreate(BaseModel):
    product_id: uuid.UUID
    label:      str
    color:      str | None = None
    quantity:   Decimal = Decimal("1")


class ButtonUpdate(BaseModel):
    label:    str | None = None
    color:    str | None = None
    quantity: Decimal | None = None


class ButtonOut(BaseModel):
    id:         uuid.UUID
    product_id: uuid.UUID
    label:      str
    color:      str | None
    quantity:   Decimal
    position:   int
    created_at: datetime


class ReorderBody(BaseModel):
    order: list[uuid.UUID]


@router.get("", response_model=list[ButtonOut])
async def list_buttons(
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _user, member = ctx
    rows = (
        await db.scalars(
            select(PosQuickButton)
            .where(PosQuickButton.org_id == member.org_id)
            .order_by(PosQuickButton.position.asc())
        )
    ).all()
    return list(rows)


@router.post("", response_model=ButtonOut, status_code=status.HTTP_201_CREATED)
async def create_button(
    body: ButtonCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    # Product must belong to the caller's org.
    product = await db.scalar(
        select(Product).where(
            Product.id == body.product_id, Product.org_id == member.org_id
        )
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    # Capacity + validation.
    positions = list(
        (
            await db.scalars(
                select(PosQuickButton.position).where(
                    PosQuickButton.org_id == member.org_id
                )
            )
        ).all()
    )
    try:
        svc.assert_capacity(len(positions))
        label = svc.validate_label(body.label)
        color = svc.validate_color(body.color)
        quantity = svc.validate_quantity(body.quantity)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    row = PosQuickButton(
        org_id=member.org_id,
        product_id=body.product_id,
        label=label,
        color=color,
        quantity=quantity,
        position=svc.next_position(positions),
    )
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="pos_quick_button.created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="pos_quick_button",
        target_id=str(row.id),
        request=request,
        extra={"product_id": str(body.product_id)},
    )
    await db.commit()
    await db.refresh(row)
    return row


@router.patch("/{button_id}", response_model=ButtonOut)
async def update_button(
    button_id: uuid.UUID,
    body: ButtonUpdate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await db.get(PosQuickButton, button_id)
    if row is None or row.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="Button not found")

    changed: list[str] = []
    try:
        if body.label is not None:
            row.label = svc.validate_label(body.label)
            changed.append("label")
        if body.color is not None:
            row.color = svc.validate_color(body.color)
            changed.append("color")
        if body.quantity is not None:
            row.quantity = svc.validate_quantity(body.quantity)
            changed.append("quantity")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if changed:
        await log_action(
            db,
            action="pos_quick_button.updated",
            org_id=member.org_id,
            actor_user_id=user["user_id"],
            target_type="pos_quick_button",
            target_id=str(row.id),
            request=request,
            extra={"fields": changed},
        )
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/{button_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_button(
    button_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await db.get(PosQuickButton, button_id)
    if row is None or row.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="Button not found")
    await db.delete(row)
    await log_action(
        db,
        action="pos_quick_button.deleted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="pos_quick_button",
        target_id=str(button_id),
        request=request,
        extra={},
    )
    await db.commit()
    return None


@router.post("/reorder", response_model=list[ButtonOut])
async def reorder_buttons(
    body: ReorderBody,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    rows = list(
        (
            await db.scalars(
                select(PosQuickButton)
                .where(PosQuickButton.org_id == member.org_id)
                .order_by(PosQuickButton.position.asc())
            )
        ).all()
    )
    existing_ids = [str(r.id) for r in rows]
    new_ids = [str(x) for x in body.order]
    try:
        pairs = svc.reorder(existing_ids, new_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    by_id = {str(r.id): r for r in rows}

    # Two-phase update to dodge the (org_id, position) UNIQUE during
    # the swap: negative positions are never used in normal flow.
    for i, r in enumerate(rows):
        r.position = -(i + 1)
    await db.flush()
    for bid, pos in pairs:
        by_id[bid].position = pos
    await db.flush()

    await log_action(
        db,
        action="pos_quick_button.reordered",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="pos_quick_button",
        target_id=None,
        request=request,
        extra={"count": len(pairs)},
    )
    await db.commit()
    # Return in the new order.
    return [by_id[bid] for bid, _pos in pairs]
