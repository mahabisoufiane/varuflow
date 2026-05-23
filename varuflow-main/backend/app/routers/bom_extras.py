"""BOM extras router: set-default, cost calculation, clone, versions."""
from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.bom import BomHeader, BomLine
from app.models.inventory import Product

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/manufacturing/boms", tags=["bom"])


def _row(obj: Any) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


@router.post("/{bom_id}/set-default")
async def set_bom_default(
    bom_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Set this BOM as the default for its product; clears is_default on all others."""
    user, member = auth
    org_id = member.org_id
    try:
        bom = (await db.execute(
            select(BomHeader).where(BomHeader.id == bom_id, BomHeader.org_id == org_id)
        )).scalar_one_or_none()
        if not bom:
            raise HTTPException(status_code=404, detail="BOM not found")

        # Clear is_default for all BOMs for this product in this org
        siblings = (await db.execute(
            select(BomHeader).where(
                BomHeader.product_id == bom.product_id,
                BomHeader.org_id == org_id,
            )
        )).scalars().all()
        for sibling in siblings:
            sibling.is_default = False

        bom.is_default = True
        await db.commit()
        await db.refresh(bom)
        return _row(bom)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"set_bom_default failed: {e}", extra={"org_id": org_id})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{bom_id}/cost")
async def get_bom_cost(
    bom_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Calculate BOM material cost by joining component products' purchase_price."""
    user, member = auth
    org_id = member.org_id
    try:
        bom = (await db.execute(
            select(BomHeader).where(BomHeader.id == bom_id, BomHeader.org_id == org_id)
        )).scalar_one_or_none()
        if not bom:
            raise HTTPException(status_code=404, detail="BOM not found")

        lines = (await db.execute(
            select(BomLine).where(BomLine.bom_id == bom_id)
        )).scalars().all()

        components = []
        total_material_cost = Decimal("0.00")

        for line in lines:
            product = (await db.execute(
                select(Product).where(Product.id == line.component_product_id)
            )).scalar_one_or_none()
            unit_cost = product.purchase_price if product else Decimal("0.00")
            line_cost = unit_cost * line.quantity
            total_material_cost += line_cost
            components.append({
                "product_id": str(line.component_product_id),
                "name": product.name if product else None,
                "quantity": float(line.quantity),
                "unit_cost": float(unit_cost),
                "line_cost": float(line_cost),
            })

        yield_pct = bom.yield_percent or Decimal("100")
        with_yield = (total_material_cost / yield_pct * Decimal("100")) if yield_pct else total_material_cost

        return {
            "bom_id": str(bom_id),
            "components": components,
            "total_material_cost": float(total_material_cost),
            "with_yield": float(with_yield),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"get_bom_cost failed: {e}", extra={"org_id": org_id})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{bom_id}/clone")
async def clone_bom(
    bom_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Clone a BOM with version incremented to max+1 for that product."""
    user, member = auth
    org_id = member.org_id
    try:
        bom = (await db.execute(
            select(BomHeader).where(BomHeader.id == bom_id, BomHeader.org_id == org_id)
        )).scalar_one_or_none()
        if not bom:
            raise HTTPException(status_code=404, detail="BOM not found")

        # Determine next version number
        max_version_result = await db.execute(
            select(func.max(BomHeader.version)).where(
                BomHeader.product_id == bom.product_id,
                BomHeader.org_id == org_id,
            )
        )
        max_version = max_version_result.scalar_one_or_none() or 0
        new_version = max_version + 1

        new_bom = BomHeader(
            org_id=org_id,
            product_id=bom.product_id,
            name=f"{bom.name} v{new_version}",
            is_kit=bom.is_kit,
            is_active=bom.is_active,
            version=new_version,
            is_default=False,
            yield_percent=bom.yield_percent,
            scrap_rate=bom.scrap_rate,
            cost_override=bom.cost_override,
        )
        db.add(new_bom)
        await db.flush()

        # Clone all lines
        original_lines = (await db.execute(
            select(BomLine).where(BomLine.bom_id == bom_id)
        )).scalars().all()

        for line in original_lines:
            new_line = BomLine(
                org_id=org_id,
                bom_id=new_bom.id,
                component_product_id=line.component_product_id,
                quantity=line.quantity,
                unit=line.unit,
                notes=line.notes,
            )
            db.add(new_line)

        await db.commit()
        await db.refresh(new_bom)
        return _row(new_bom)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"clone_bom failed: {e}", extra={"org_id": org_id})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{bom_id}/versions")
async def list_bom_versions(
    bom_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """List all BOM versions for the same product_id + org_id, newest first."""
    user, member = auth
    org_id = member.org_id
    try:
        bom = (await db.execute(
            select(BomHeader).where(BomHeader.id == bom_id, BomHeader.org_id == org_id)
        )).scalar_one_or_none()
        if not bom:
            raise HTTPException(status_code=404, detail="BOM not found")

        versions = (await db.execute(
            select(BomHeader).where(
                BomHeader.product_id == bom.product_id,
                BomHeader.org_id == org_id,
            ).order_by(BomHeader.version.desc())
        )).scalars().all()

        return [_row(v) for v in versions]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_bom_versions failed: {e}", extra={"org_id": org_id})
        raise HTTPException(status_code=500, detail="Internal server error")
