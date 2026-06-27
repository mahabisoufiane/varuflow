"""Admin router for managing online (storefront) orders.

All endpoints require a valid Supabase session (get_current_member).
Data is always scoped to the requesting org.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_member
from .models import OnlineOrder, OnlineOrderItem, Storefront
from app.features.auth.organization import OrganizationMember
from app.middleware.plan_check import require_module

log = logging.getLogger(__name__)

router = APIRouter(
    dependencies=[Depends(require_module("invoicing"))],
)


async def _get_order(
    order_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession,
) -> OnlineOrder:
    order = (
        await db.execute(
            select(OnlineOrder)
            .options(selectinload(OnlineOrder.items))
            .where(OnlineOrder.id == order_id, OnlineOrder.org_id == org_id)
        )
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def _order_out(order: OnlineOrder) -> dict:
    return {
        "id": str(order.id),
        "order_number": order.order_number,
        "status": order.status,
        "customer_name": order.customer_name,
        "customer_email": order.customer_email,
        "shipping_address": order.shipping_address,
        "subtotal": str(order.subtotal),
        "vat_amount": str(order.vat_amount),
        "total": str(order.total),
        "shipping_cost": str(order.shipping_cost),
        "payment_method": order.payment_method,
        "shipping_carrier": order.shipping_carrier,
        "tracking_number": order.tracking_number,
        "tracking_url": order.tracking_url,
        "nshift_shipment_id": order.nshift_shipment_id,
        "confirmed_at": order.confirmed_at.isoformat() if order.confirmed_at else None,
        "shipped_at": order.shipped_at.isoformat() if order.shipped_at else None,
        "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
        "cancelled_at": order.cancelled_at.isoformat() if order.cancelled_at else None,
        "created_at": order.created_at.isoformat(),
        "items": [
            {
                "id": str(it.id),
                "product_id": str(it.product_id) if it.product_id else None,
                "description": it.description,
                "quantity": it.quantity,
                "unit_price": str(it.unit_price),
                "tax_rate": str(it.tax_rate),
                "line_total": str(it.line_total),
            }
            for it in (order.items or [])
        ],
    }


@router.get("/api/shop/orders")
async def list_orders(
    page: int = 1,
    per_page: int = 50,
    status: Optional[str] = None,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _, member = ctx
        org_id = member.org_id
        offset = (page - 1) * per_page

        q = (
            select(OnlineOrder)
            .where(OnlineOrder.org_id == org_id)
            .order_by(OnlineOrder.created_at.desc())
            .offset(offset)
            .limit(per_page)
        )
        if status:
            q = q.where(OnlineOrder.status == status.upper())

        rows = (await db.execute(q)).scalars().all()
        return {"items": [_order_out(o) for o in rows], "page": page, "per_page": per_page}
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_orders failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/shop/orders/{order_id}")
async def get_order(
    order_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _, member = ctx
        order = await _get_order(order_id, member.org_id, db)
        return _order_out(order)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_order failed id=%s: %s", order_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


class PatchOrderBody(BaseModel):
    tracking_number: Optional[str] = None
    tracking_url: Optional[str] = None
    shipping_carrier: Optional[str] = None


@router.patch("/api/shop/orders/{order_id}")
async def patch_order(
    order_id: uuid.UUID,
    body: PatchOrderBody,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _, member = ctx
        order = await _get_order(order_id, member.org_id, db)
        if body.tracking_number is not None:
            order.tracking_number = body.tracking_number
        if body.tracking_url is not None:
            order.tracking_url = body.tracking_url
        if body.shipping_carrier is not None:
            order.shipping_carrier = body.shipping_carrier.upper()
        await db.commit()
        return _order_out(order)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_order failed id=%s: %s", order_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/shop/orders/{order_id}/confirm")
async def confirm_order(
    order_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _, member = ctx
        order = await _get_order(order_id, member.org_id, db)
        if order.status not in ("PENDING",):
            raise HTTPException(status_code=400, detail=f"Cannot confirm order in status {order.status}")
        order.status = "CONFIRMED"
        order.confirmed_at = datetime.now(timezone.utc)
        await db.commit()

        try:
            from app.services.email import send_order_confirmation_storefront
            sf = await db.get(Storefront, order.storefront_id)
            items_data = [
                {"description": it.description, "qty": it.quantity, "unit_price": str(it.unit_price)}
                for it in (order.items or [])
            ]
            await send_order_confirmation_storefront(
                to_email=order.customer_email,
                customer_name=order.customer_name,
                order_number=order.order_number,
                items=items_data,
                total=str(order.total),
                currency=sf.currency if sf else "SEK",
                shop_name=sf.name if sf else "Shop",
                shop_url=f"{settings.FRONTEND_URL}/shop/{sf.slug if sf else ''}",
            )
        except Exception:
            log.exception("confirm_order: confirmation email failed for %s", order.id)

        return _order_out(order)
    except HTTPException:
        raise
    except Exception as e:
        log.error("confirm_order failed id=%s: %s", order_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


class ShipOrderBody(BaseModel):
    carrier: str = "POSTNORD"
    weight_kg: float = 1.0


@router.post("/api/shop/orders/{order_id}/ship")
async def ship_order(
    order_id: uuid.UUID,
    body: ShipOrderBody,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _, member = ctx
        order = await _get_order(order_id, member.org_id, db)
        if order.status not in ("CONFIRMED", "PENDING"):
            raise HTTPException(status_code=400, detail=f"Cannot ship order in status {order.status}")

        items_description = ", ".join(it.description for it in (order.items or []))[:50]

        from app.services.nshift import create_shipment
        shipment = await create_shipment(
            order_number=order.order_number,
            customer_name=order.customer_name,
            shipping_address=order.shipping_address or {},
            items_description=items_description,
            weight_kg=body.weight_kg,
            carrier=body.carrier,
        )

        if shipment:
            order.nshift_shipment_id = shipment["shipment_id"]
            order.tracking_number = shipment["tracking_number"]
            order.tracking_url = shipment["tracking_url"]

        order.status = "SHIPPED"
        order.shipping_carrier = body.carrier.upper()
        order.shipped_at = datetime.now(timezone.utc)
        await db.commit()

        result = _order_out(order)
        if shipment:
            result["label_pdf_base64"] = shipment.get("label_pdf_base64")
        return result
    except HTTPException:
        raise
    except Exception as e:
        log.error("ship_order failed id=%s: %s", order_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/shop/orders/{order_id}/cancel")
async def cancel_order(
    order_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _, member = ctx
        order = await _get_order(order_id, member.org_id, db)
        if order.status in ("CANCELLED", "REFUNDED"):
            raise HTTPException(status_code=400, detail=f"Order is already {order.status}")

        # Attempt Stripe refund if payment intent exists
        if order.stripe_payment_intent_id and settings.STRIPE_SECRET_KEY:
            try:
                stripe.api_key = settings.STRIPE_SECRET_KEY
                stripe.Refund.create(payment_intent=order.stripe_payment_intent_id)
                order.status = "REFUNDED"
            except stripe.StripeError as se:
                log.error("Stripe refund failed for order %s: %s", order.id, se)
                order.status = "CANCELLED"
        else:
            order.status = "CANCELLED"

        order.cancelled_at = datetime.now(timezone.utc)
        await db.commit()
        return _order_out(order)
    except HTTPException:
        raise
    except Exception as e:
        log.error("cancel_order failed id=%s: %s", order_id, e)
        raise HTTPException(status_code=500, detail="Internal server error")
