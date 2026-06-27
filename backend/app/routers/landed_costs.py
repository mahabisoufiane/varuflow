"""Landed costs router: track freight/customs/insurance charges on POs."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.inventory import Product
from app.models.landed_costs import LandedCostCharge, LandedCostLine

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/landed-costs", tags=["landed_costs"])


def _row(obj: Any) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


# ── Schemas ──────────────────────────────────────────────────────────────────

class ChargeCreate(BaseModel):
    purchase_order_id: Optional[uuid.UUID] = None
    charge_type: str
    total_amount: Decimal
    currency: str = "SEK"
    distribution_method: str = "by_value"
    notes: Optional[str] = None


class ChargeUpdate(BaseModel):
    charge_type: Optional[str] = None
    total_amount: Optional[Decimal] = None
    distribution_method: Optional[str] = None
    notes: Optional[str] = None


class LineCreate(BaseModel):
    product_id: Optional[uuid.UUID] = None
    purchase_order_item_id: Optional[uuid.UUID] = None
    quantity: Optional[Decimal] = None
    unit_weight: Optional[Decimal] = None
    item_value: Optional[Decimal] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_charges(
    purchase_order_id: Optional[uuid.UUID] = None,
    is_applied: Optional[bool] = None,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        q = select(LandedCostCharge).where(LandedCostCharge.org_id == org_id)
        if purchase_order_id is not None:
            q = q.where(LandedCostCharge.purchase_order_id == purchase_order_id)
        if is_applied is not None:
            q = q.where(LandedCostCharge.is_applied == is_applied)
        charges = (await db.execute(q.order_by(LandedCostCharge.created_at.desc()))).scalars().all()
        return [_row(c) for c in charges]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_charges failed: {e}", extra={"org_id": org_id})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_charge(
    body: ChargeCreate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        charge = LandedCostCharge(
            org_id=org_id,
            purchase_order_id=body.purchase_order_id,
            charge_type=body.charge_type,
            total_amount=body.total_amount,
            currency=body.currency,
            distribution_method=body.distribution_method,
            notes=body.notes,
        )
        db.add(charge)
        await db.commit()
        await db.refresh(charge)
        return _row(charge)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_charge failed: {e}", extra={"org_id": org_id})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/report")
async def landed_cost_report(
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """List applied charges grouped by PO with freight % of merchandise value."""
    user, member = auth
    org_id = member.org_id
    try:
        charges = (await db.execute(
            select(LandedCostCharge).where(
                LandedCostCharge.org_id == org_id,
                LandedCostCharge.is_applied == True,
            ).order_by(LandedCostCharge.purchase_order_id, LandedCostCharge.created_at)
        )).scalars().all()

        # Group by purchase_order_id
        by_po: dict = {}
        for charge in charges:
            po_key = str(charge.purchase_order_id) if charge.purchase_order_id else "no_po"
            if po_key not in by_po:
                by_po[po_key] = {"purchase_order_id": po_key, "charges": [], "total_freight": Decimal("0"), "total_merchandise": Decimal("0")}
            by_po[po_key]["charges"].append(_row(charge))
            if charge.charge_type == "freight":
                by_po[po_key]["total_freight"] += charge.total_amount

            # Sum merchandise value from lines
            lines = (await db.execute(
                select(LandedCostLine).where(LandedCostLine.charge_id == charge.id)
            )).scalars().all()
            for line in lines:
                if line.item_value:
                    by_po[po_key]["total_merchandise"] += line.item_value

        result = []
        for po_key, data in by_po.items():
            freight_pct = None
            if data["total_merchandise"] > 0:
                freight_pct = float(data["total_freight"] / data["total_merchandise"] * 100)
            result.append({
                "purchase_order_id": data["purchase_order_id"],
                "charges": data["charges"],
                "total_freight": float(data["total_freight"]),
                "total_merchandise": float(data["total_merchandise"]),
                "freight_pct_of_merchandise": freight_pct,
            })

        return result
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"landed_cost_report failed: {e}", extra={"org_id": org_id})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{charge_id}")
async def get_charge(
    charge_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        charge = (await db.execute(
            select(LandedCostCharge).where(
                LandedCostCharge.id == charge_id,
                LandedCostCharge.org_id == org_id,
            )
        )).scalar_one_or_none()
        if not charge:
            raise HTTPException(status_code=404, detail="Charge not found")

        lines = (await db.execute(
            select(LandedCostLine).where(LandedCostLine.charge_id == charge_id)
        )).scalars().all()

        result = _row(charge)
        result["lines"] = [_row(l) for l in lines]
        return result
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"get_charge failed: {e}", extra={"org_id": org_id})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{charge_id}")
async def update_charge(
    charge_id: uuid.UUID,
    body: ChargeUpdate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        charge = (await db.execute(
            select(LandedCostCharge).where(
                LandedCostCharge.id == charge_id,
                LandedCostCharge.org_id == org_id,
            )
        )).scalar_one_or_none()
        if not charge:
            raise HTTPException(status_code=404, detail="Charge not found")

        if body.charge_type is not None:
            charge.charge_type = body.charge_type
        if body.total_amount is not None:
            charge.total_amount = body.total_amount
        if body.distribution_method is not None:
            charge.distribution_method = body.distribution_method
        if body.notes is not None:
            charge.notes = body.notes

        await db.commit()
        await db.refresh(charge)
        return _row(charge)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"update_charge failed: {e}", extra={"org_id": org_id})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{charge_id}", status_code=204)
async def delete_charge(
    charge_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        charge = (await db.execute(
            select(LandedCostCharge).where(
                LandedCostCharge.id == charge_id,
                LandedCostCharge.org_id == org_id,
            )
        )).scalar_one_or_none()
        if not charge:
            raise HTTPException(status_code=404, detail="Charge not found")
        if charge.is_applied:
            raise HTTPException(status_code=400, detail="Cannot delete an applied charge")

        await db.delete(charge)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"delete_charge failed: {e}", extra={"org_id": org_id})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{charge_id}/lines", status_code=201)
async def add_line(
    charge_id: uuid.UUID,
    body: LineCreate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        charge = (await db.execute(
            select(LandedCostCharge).where(
                LandedCostCharge.id == charge_id,
                LandedCostCharge.org_id == org_id,
            )
        )).scalar_one_or_none()
        if not charge:
            raise HTTPException(status_code=404, detail="Charge not found")

        line = LandedCostLine(
            charge_id=charge_id,
            product_id=body.product_id,
            purchase_order_item_id=body.purchase_order_item_id,
            quantity=body.quantity,
            unit_weight=body.unit_weight,
            item_value=body.item_value,
        )
        db.add(line)
        await db.commit()
        await db.refresh(line)
        return _row(line)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"add_line failed: {e}", extra={"org_id": org_id})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{charge_id}/lines/{line_id}", status_code=204)
async def delete_line(
    charge_id: uuid.UUID,
    line_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        charge = (await db.execute(
            select(LandedCostCharge).where(
                LandedCostCharge.id == charge_id,
                LandedCostCharge.org_id == org_id,
            )
        )).scalar_one_or_none()
        if not charge:
            raise HTTPException(status_code=404, detail="Charge not found")

        line = (await db.execute(
            select(LandedCostLine).where(
                LandedCostLine.id == line_id,
                LandedCostLine.charge_id == charge_id,
            )
        )).scalar_one_or_none()
        if not line:
            raise HTTPException(status_code=404, detail="Line not found")

        await db.delete(line)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"delete_line failed: {e}", extra={"org_id": org_id})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{charge_id}/distribute")
async def distribute_charge(
    charge_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Recalculate allocated_amount on each line using the distribution_method."""
    user, member = auth
    org_id = member.org_id
    try:
        charge = (await db.execute(
            select(LandedCostCharge).where(
                LandedCostCharge.id == charge_id,
                LandedCostCharge.org_id == org_id,
            )
        )).scalar_one_or_none()
        if not charge:
            raise HTTPException(status_code=404, detail="Charge not found")

        lines = (await db.execute(
            select(LandedCostLine).where(LandedCostLine.charge_id == charge_id)
        )).scalars().all()

        if not lines:
            return {"lines": []}

        method = charge.distribution_method
        total_amount = charge.total_amount

        # Compute denominator based on method
        if method == "by_value":
            total_base = sum((l.item_value or Decimal("0")) for l in lines)
            def get_share(line):
                return (line.item_value or Decimal("0")) / total_base if total_base else Decimal("0")
        elif method == "by_quantity":
            total_base = sum((l.quantity or Decimal("0")) for l in lines)
            def get_share(line):
                return (line.quantity or Decimal("0")) / total_base if total_base else Decimal("0")
        elif method == "by_weight":
            total_base = sum((l.unit_weight or Decimal("0")) for l in lines)
            def get_share(line):
                return (line.unit_weight or Decimal("0")) / total_base if total_base else Decimal("0")
        else:
            # manual — do not recalculate
            return {"lines": [_row(l) for l in lines]}

        for line in lines:
            share = get_share(line)
            line.allocated_amount = (total_amount * share).quantize(Decimal("0.01"))
            qty = line.quantity or Decimal("0")
            line.applied_unit_cost = (line.allocated_amount / qty).quantize(Decimal("0.01")) if qty else None

        await db.commit()
        for line in lines:
            await db.refresh(line)

        return {"lines": [_row(l) for l in lines]}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"distribute_charge failed: {e}", extra={"org_id": org_id})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{charge_id}/apply")
async def apply_charge(
    charge_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Mark charge as applied and update product purchase_prices."""
    user, member = auth
    org_id = member.org_id
    try:
        charge = (await db.execute(
            select(LandedCostCharge).where(
                LandedCostCharge.id == charge_id,
                LandedCostCharge.org_id == org_id,
            )
        )).scalar_one_or_none()
        if not charge:
            raise HTTPException(status_code=404, detail="Charge not found")
        if charge.is_applied:
            raise HTTPException(status_code=400, detail="Charge already applied")

        lines = (await db.execute(
            select(LandedCostLine).where(LandedCostLine.charge_id == charge_id)
        )).scalars().all()

        # Update product purchase_prices
        for line in lines:
            if line.product_id and line.applied_unit_cost:
                product = (await db.execute(
                    select(Product).where(Product.id == line.product_id)
                )).scalar_one_or_none()
                if product:
                    product.purchase_price = product.purchase_price + line.applied_unit_cost

        charge.is_applied = True
        charge.applied_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(charge)
        return _row(charge)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"apply_charge failed: {e}", extra={"org_id": org_id})
        raise HTTPException(status_code=500, detail="Internal server error")
