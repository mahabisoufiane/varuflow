"""Negotiated pricing visibility for buyers — Sprint 10.

Endpoints under ``/api/negotiated-pricing``:

    GET    /{customer_id}           list all price overrides for this customer
    GET    /{customer_id}/summary   count + avg discount pct
"""
from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.customer_price_override import CustomerPriceOverride

router = APIRouter(prefix="/api/negotiated-pricing", tags=["negotiated-pricing"], dependencies=[Depends(require_module("crm"))])
logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────────────

class PriceOverrideOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    product_id: uuid.UUID
    override_price: Decimal
    product_name: str | None = None


class NegotiatedPricingSummary(BaseModel):
    customer_id: uuid.UUID
    total_overrides: int
    avg_override_price: Decimal | None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{customer_id}", response_model=list[PriceOverrideOut])
async def list_negotiated_prices(
    customer_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        # Try to join with products table for name; fall back gracefully if unavailable
        try:
            from app.models.inventory import Product
            stmt = (
                select(CustomerPriceOverride, Product.name.label("product_name"))
                .outerjoin(Product, Product.id == CustomerPriceOverride.product_id)
                .where(
                    CustomerPriceOverride.org_id == member.org_id,
                    CustomerPriceOverride.customer_id == customer_id,
                )
                .order_by(CustomerPriceOverride.product_id)
                .limit(limit)
                .offset(offset)
            )
            results = (await db.execute(stmt)).all()
            return [
                PriceOverrideOut(
                    id=row.CustomerPriceOverride.id,
                    customer_id=row.CustomerPriceOverride.customer_id,
                    product_id=row.CustomerPriceOverride.product_id,
                    override_price=row.CustomerPriceOverride.override_price,
                    product_name=row.product_name,
                )
                for row in results
            ]
        except Exception:
            # Fallback: query without join
            stmt = (
                select(CustomerPriceOverride)
                .where(
                    CustomerPriceOverride.org_id == member.org_id,
                    CustomerPriceOverride.customer_id == customer_id,
                )
                .order_by(CustomerPriceOverride.product_id)
                .limit(limit)
                .offset(offset)
            )
            rows = (await db.scalars(stmt)).all()
            return [
                PriceOverrideOut(
                    id=r.id,
                    customer_id=r.customer_id,
                    product_id=r.product_id,
                    override_price=r.override_price,
                )
                for r in rows
            ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_negotiated_prices failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{customer_id}/summary", response_model=NegotiatedPricingSummary)
async def negotiated_pricing_summary(
    customer_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        stmt = select(
            func.count(CustomerPriceOverride.id).label("total"),
            func.avg(CustomerPriceOverride.override_price).label("avg_price"),
        ).where(
            CustomerPriceOverride.org_id == member.org_id,
            CustomerPriceOverride.customer_id == customer_id,
        )
        result = (await db.execute(stmt)).one()
        return NegotiatedPricingSummary(
            customer_id=customer_id,
            total_overrides=int(result.total or 0),
            avg_override_price=Decimal(str(result.avg_price)) if result.avg_price is not None else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"negotiated_pricing_summary failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
