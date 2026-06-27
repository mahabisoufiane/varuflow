"""Kitting and Assembly router.

Kits bundle multiple component SKUs into one finished kit SKU.
Assembly deducts component stock and increments kit product stock.
Disassembly reverses the process.
"""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.inventory import Product, StockLevel, Warehouse
from app.models.kits import KitAssembly, KitComponent, KitDefinition

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/kits", tags=["kitting"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ComponentIn(BaseModel):
    component_product_id: uuid.UUID
    quantity: float = Field(gt=0)


class KitCreateIn(BaseModel):
    product_id: uuid.UUID
    name: str
    description: Optional[str] = None
    custom_price: Optional[float] = None
    components: list[ComponentIn] = Field(default_factory=list)


class KitUpdateIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    custom_price: Optional[float] = None
    is_active: Optional[bool] = None


class AssembleIn(BaseModel):
    quantity: float = Field(gt=0)
    notes: Optional[str] = None
    direction: str = Field(default="assemble", pattern="^(assemble|disassemble)$")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_kit(kit_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession) -> KitDefinition:
    result = await db.execute(
        select(KitDefinition)
        .options(selectinload(KitDefinition.components))
        .where(KitDefinition.id == kit_id, KitDefinition.org_id == org_id)
    )
    kit = result.scalar_one_or_none()
    if not kit:
        raise HTTPException(status_code=404, detail="Kit not found")
    return kit


async def _total_stock(product_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession) -> float:
    result = await db.execute(
        select(func.coalesce(func.sum(StockLevel.quantity), 0))
        .where(StockLevel.product_id == product_id, StockLevel.org_id == org_id)
    )
    return float(result.scalar() or 0)


async def _first_warehouse_id(org_id: uuid.UUID, db: AsyncSession) -> Optional[uuid.UUID]:
    result = await db.execute(
        select(Warehouse.id).where(Warehouse.org_id == org_id).limit(1)
    )
    return result.scalar_one_or_none()


async def _adjust_stock(
    product_id: uuid.UUID,
    org_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    delta: float,
    db: AsyncSession,
) -> None:
    """Add delta (positive or negative) to the stock level row."""
    result = await db.execute(
        select(StockLevel).where(
            StockLevel.product_id == product_id,
            StockLevel.org_id == org_id,
            StockLevel.warehouse_id == warehouse_id,
        )
    )
    sl = result.scalar_one_or_none()
    if sl:
        sl.quantity = max(0, sl.quantity + delta)
    else:
        db.add(StockLevel(
            id=uuid.uuid4(),
            org_id=org_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity=max(0, delta),
        ))


async def _component_availability(kit: KitDefinition, org_id: uuid.UUID, db: AsyncSession) -> dict:
    """Return max kits assembable and per-component stock."""
    details = []
    max_kits = float("inf")
    for comp in kit.components:
        stock = await _total_stock(comp.component_product_id, org_id, db)
        possible = stock / float(comp.quantity) if float(comp.quantity) > 0 else 0
        max_kits = min(max_kits, possible)
        details.append({
            "component_product_id": str(comp.component_product_id),
            "quantity_required_per_kit": float(comp.quantity),
            "stock_available": stock,
            "kits_possible_from_this_component": possible,
        })
    return {
        "max_kits_assembleable": int(max_kits) if max_kits != float("inf") else 0,
        "components": details,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_kits(
    active_only: bool = Query(True),
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        q = (
            select(KitDefinition)
            .options(selectinload(KitDefinition.components))
            .where(KitDefinition.org_id == org_id)
        )
        if active_only:
            q = q.where(KitDefinition.is_active.is_(True))
        result = await db.execute(q.order_by(KitDefinition.name))
        kits = result.scalars().all()

        out = []
        for kit in kits:
            avail = await _component_availability(kit, org_id, db)
            kit_product = await db.get(Product, kit.product_id)
            comp_cost = 0.0
            for comp in kit.components:
                p = await db.get(Product, comp.component_product_id)
                if p:
                    comp_cost += float(p.purchase_price) * float(comp.quantity)
            kit_price = float(kit.custom_price) if kit.custom_price else comp_cost
            out.append({
                "id": str(kit.id),
                "product_id": str(kit.product_id),
                "product_name": kit_product.name if kit_product else None,
                "name": kit.name,
                "description": kit.description,
                "custom_price": float(kit.custom_price) if kit.custom_price else None,
                "effective_price": kit_price,
                "component_cost": comp_cost,
                "margin_percent": round((kit_price - comp_cost) / kit_price * 100, 2) if kit_price else 0,
                "is_active": kit.is_active,
                "components": [
                    {"component_product_id": str(c.component_product_id), "quantity": float(c.quantity)}
                    for c in kit.components
                ],
                "availability": avail,
            })
        return {"items": out, "total": len(out)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_kits failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_kit(
    body: KitCreateIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        kit = KitDefinition(
            id=uuid.uuid4(),
            org_id=org_id,
            product_id=body.product_id,
            name=body.name,
            description=body.description,
            custom_price=body.custom_price,
        )
        db.add(kit)
        await db.flush()
        for comp in body.components:
            db.add(KitComponent(
                id=uuid.uuid4(),
                kit_id=kit.id,
                component_product_id=comp.component_product_id,
                quantity=comp.quantity,
            ))
        await db.commit()
        await db.refresh(kit)
        return {"id": str(kit.id), "name": kit.name}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"create_kit failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{kit_id}")
async def get_kit(
    kit_id: uuid.UUID,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        kit = await _get_kit(kit_id, org_id, db)
        avail = await _component_availability(kit, org_id, db)
        return {"id": str(kit.id), "name": kit.name, "description": kit.description,
                "product_id": str(kit.product_id), "custom_price": float(kit.custom_price) if kit.custom_price else None,
                "is_active": kit.is_active, "availability": avail,
                "components": [{"component_product_id": str(c.component_product_id), "quantity": float(c.quantity)} for c in kit.components]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_kit failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{kit_id}")
async def update_kit(
    kit_id: uuid.UUID,
    body: KitUpdateIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        kit = await _get_kit(kit_id, org_id, db)
        if body.name is not None:
            kit.name = body.name
        if body.description is not None:
            kit.description = body.description
        if body.custom_price is not None:
            kit.custom_price = body.custom_price
        if body.is_active is not None:
            kit.is_active = body.is_active
        await db.commit()
        return {"id": str(kit.id), "name": kit.name}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"update_kit failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{kit_id}/components")
async def replace_components(
    kit_id: uuid.UUID,
    components: list[ComponentIn],
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Replace all components of a kit."""
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        kit = await _get_kit(kit_id, org_id, db)
        for comp in kit.components:
            await db.delete(comp)
        await db.flush()
        for comp in components:
            db.add(KitComponent(id=uuid.uuid4(), kit_id=kit.id, component_product_id=comp.component_product_id, quantity=comp.quantity))
        await db.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"replace_components failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{kit_id}/assemble")
async def assemble_kit(
    kit_id: uuid.UUID,
    body: AssembleIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Assemble or disassemble kits, adjusting stock accordingly."""
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        kit = await _get_kit(kit_id, org_id, db)

        warehouse_id = await _first_warehouse_id(org_id, db)
        if not warehouse_id:
            raise HTTPException(status_code=422, detail="No warehouse configured for this org")

        if body.direction == "assemble":
            # Check each component has enough stock
            avail = await _component_availability(kit, org_id, db)
            if avail["max_kits_assembleable"] < body.quantity:
                raise HTTPException(
                    status_code=422,
                    detail=f"Insufficient component stock. Max assembleable: {avail['max_kits_assembleable']}"
                )
            # Deduct components, add kit stock
            for comp in kit.components:
                await _adjust_stock(comp.component_product_id, org_id, warehouse_id, -float(comp.quantity) * body.quantity, db)
            await _adjust_stock(kit.product_id, org_id, warehouse_id, body.quantity, db)
        else:
            # Disassemble: check kit stock
            kit_stock = await _total_stock(kit.product_id, org_id, db)
            if kit_stock < body.quantity:
                raise HTTPException(status_code=422, detail=f"Insufficient kit stock. Available: {kit_stock}")
            await _adjust_stock(kit.product_id, org_id, warehouse_id, -body.quantity, db)
            for comp in kit.components:
                await _adjust_stock(comp.component_product_id, org_id, warehouse_id, float(comp.quantity) * body.quantity, db)

        # Record assembly log
        db.add(KitAssembly(
            id=uuid.uuid4(),
            org_id=org_id,
            kit_id=kit.id,
            direction=body.direction,
            quantity=body.quantity,
            notes=body.notes,
            assembled_by_staff_id=member.get("user_id"),
        ))
        await db.commit()
        return {"ok": True, "direction": body.direction, "quantity": body.quantity}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"assemble_kit failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{kit_id}/assemblies")
async def assembly_log(
    kit_id: uuid.UUID,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        await _get_kit(kit_id, org_id, db)  # auth check
        result = await db.execute(
            select(KitAssembly)
            .where(KitAssembly.kit_id == kit_id, KitAssembly.org_id == org_id)
            .order_by(KitAssembly.assembled_at.desc())
            .limit(limit).offset(offset)
        )
        rows = result.scalars().all()
        return {
            "items": [
                {"id": str(r.id), "direction": r.direction, "quantity": float(r.quantity),
                 "notes": r.notes, "assembled_at": r.assembled_at.isoformat()}
                for r in rows
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"assembly_log failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")
