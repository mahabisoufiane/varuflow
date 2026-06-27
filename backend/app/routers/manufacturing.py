"""Manufacturing router: BOMs, work orders, planning, kits."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.bom import BomHeader, BomLine
from app.models.inventory import Product, StockLevel, StockMovement, StockMovementType
from app.models.work_orders_mfg import WorkOrder, WorkOrderLabourLine, WorkOrderMaterialLine

log = logging.getLogger(__name__)
router = APIRouter()

VALID_WO_STATUSES = {"draft", "planned", "in_progress", "completed", "cancelled"}


# ── Schemas ──────────────────────────────────────────────────────────────────

class BomCreate(BaseModel):
    product_id: uuid.UUID
    name: str
    is_kit: bool = False


class BomUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    is_kit: Optional[bool] = None


class BomLineCreate(BaseModel):
    component_product_id: uuid.UUID
    quantity: Decimal
    unit: str = "st"
    notes: Optional[str] = None


class BomLineUpdate(BaseModel):
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    notes: Optional[str] = None


class WorkOrderCreate(BaseModel):
    bom_id: uuid.UUID
    warehouse_id: uuid.UUID
    planned_qty: int = 1
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    notes: Optional[str] = None


class WorkOrderUpdate(BaseModel):
    notes: Optional[str] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    planned_qty: Optional[int] = None


class WorkOrderComplete(BaseModel):
    produced_qty: int
    material_actuals: Optional[list[dict]] = None  # [{line_id, actual_qty}]


class LabourLineCreate(BaseModel):
    operator_name: str
    hours: Decimal
    hourly_rate: Optional[Decimal] = None
    notes: Optional[str] = None


class FeasibilityCheck(BaseModel):
    bom_id: uuid.UUID
    qty: int
    warehouse_id: uuid.UUID


class KitBuild(BaseModel):
    qty: int
    warehouse_id: uuid.UUID


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row(obj: Any) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


async def _next_order_number(db: AsyncSession, org_id: uuid.UUID) -> str:
    count = (await db.execute(
        select(func.count()).where(WorkOrder.org_id == org_id)
    )).scalar_one()
    return f"WO-{count + 1:04d}"


async def _complete_work_order(
    db: AsyncSession,
    wo: WorkOrder,
    produced_qty: int,
    material_actuals: Optional[list[dict]],
    org_id: uuid.UUID,
) -> list[dict]:
    """Apply stock movements for a completed work order. Returns summary of movements."""
    now = datetime.now(timezone.utc)
    movements_summary = []

    # Build actuals map if provided
    actuals_map: dict[str, Decimal] = {}
    if material_actuals:
        for item in material_actuals:
            actuals_map[str(item["line_id"])] = Decimal(str(item["actual_qty"]))

    # Fetch BOM to get finished-goods product_id
    bom = (await db.execute(
        select(BomHeader).where(BomHeader.id == wo.bom_id)
    )).scalar_one_or_none()
    if not bom:
        raise HTTPException(status_code=404, detail="BOM not found")

    # OUT movements for each material line consumed
    for line in wo.material_lines:
        qty_used = actuals_map.get(str(line.id), None)
        if qty_used is None:
            qty_used = line.planned_qty * produced_qty
        else:
            qty_used = Decimal(str(qty_used))

        # Update actual_qty on the line
        line.actual_qty = qty_used

        consumed_int = int(qty_used)
        if consumed_int > 0:
            movement = StockMovement(
                id=uuid.uuid4(),
                org_id=org_id,
                product_id=line.product_id,
                warehouse_id=wo.warehouse_id,
                type=StockMovementType.OUT,
                quantity=consumed_int,
                reference=wo.order_number,
                note=f"Production consumption — {wo.order_number}",
            )
            db.add(movement)

            # Decrement StockLevel
            sl = (await db.execute(
                select(StockLevel).where(
                    and_(
                        StockLevel.org_id == org_id,
                        StockLevel.product_id == line.product_id,
                        StockLevel.warehouse_id == wo.warehouse_id,
                    )
                )
            )).scalar_one_or_none()
            if sl:
                sl.quantity = max(0, sl.quantity - consumed_int)

            movements_summary.append({"type": "OUT", "product_id": str(line.product_id), "qty": consumed_int})

    # IN movement for finished goods
    if produced_qty > 0:
        fg_movement = StockMovement(
            id=uuid.uuid4(),
            org_id=org_id,
            product_id=bom.product_id,
            warehouse_id=wo.warehouse_id,
            type=StockMovementType.IN,
            quantity=produced_qty,
            reference=wo.order_number,
            note=f"Production output — {wo.order_number}",
        )
        db.add(fg_movement)

        # Upsert StockLevel for finished goods
        fg_sl = (await db.execute(
            select(StockLevel).where(
                and_(
                    StockLevel.org_id == org_id,
                    StockLevel.product_id == bom.product_id,
                    StockLevel.warehouse_id == wo.warehouse_id,
                )
            )
        )).scalar_one_or_none()
        if fg_sl:
            fg_sl.quantity += produced_qty
        else:
            db.add(StockLevel(
                id=uuid.uuid4(),
                org_id=org_id,
                product_id=bom.product_id,
                warehouse_id=wo.warehouse_id,
                quantity=produced_qty,
            ))

        movements_summary.append({"type": "IN", "product_id": str(bom.product_id), "qty": produced_qty})

    wo.status = "completed"
    wo.produced_qty = produced_qty
    wo.actual_end = now

    return movements_summary


# ── BOM endpoints ─────────────────────────────────────────────────────────────

@router.get("/api/manufacturing/boms")
async def list_boms(
    is_kit: Optional[bool] = None,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        q = select(BomHeader).where(BomHeader.org_id == org_id)
        if is_kit is not None:
            q = q.where(BomHeader.is_kit == is_kit)
        boms = (await db.execute(q.order_by(BomHeader.name))).scalars().all()
        result = []
        for b in boms:
            lines = (await db.execute(
                select(BomLine).where(BomLine.bom_id == b.id)
            )).scalars().all()
            d = _row(b)
            d["lines"] = [_row(l) for l in lines]
            result.append(d)
        return result
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_boms failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/manufacturing/boms", status_code=201)
async def create_bom(
    body: BomCreate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = BomHeader(id=uuid.uuid4(), org_id=org_id, **body.model_dump())
        db.add(row)
        await db.commit()
        await db.refresh(row)
        d = _row(row)
        d["lines"] = []
        return d
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_bom failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/manufacturing/boms/{bom_id}")
async def get_bom(
    bom_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(BomHeader).where(and_(BomHeader.org_id == org_id, BomHeader.id == bom_id))
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="BOM not found")
        lines = (await db.execute(select(BomLine).where(BomLine.bom_id == bom_id))).scalars().all()
        d = _row(row)
        d["lines"] = [_row(l) for l in lines]
        return d
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"get_bom failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/manufacturing/boms/{bom_id}")
async def update_bom(
    bom_id: uuid.UUID,
    body: BomUpdate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(BomHeader).where(and_(BomHeader.org_id == org_id, BomHeader.id == bom_id))
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="BOM not found")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        await db.commit()
        await db.refresh(row)
        return _row(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"update_bom failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/manufacturing/boms/{bom_id}", status_code=204)
async def delete_bom(
    bom_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(BomHeader).where(and_(BomHeader.org_id == org_id, BomHeader.id == bom_id))
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="BOM not found")
        await db.delete(row)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"delete_bom failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/manufacturing/boms/{bom_id}/lines", status_code=201)
async def add_bom_line(
    bom_id: uuid.UUID,
    body: BomLineCreate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        bom = (await db.execute(
            select(BomHeader).where(and_(BomHeader.org_id == org_id, BomHeader.id == bom_id))
        )).scalar_one_or_none()
        if not bom:
            raise HTTPException(status_code=404, detail="BOM not found")
        line = BomLine(id=uuid.uuid4(), org_id=org_id, bom_id=bom_id, **body.model_dump())
        db.add(line)
        await db.commit()
        await db.refresh(line)
        return _row(line)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"add_bom_line failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/manufacturing/boms/{bom_id}/lines/{line_id}")
async def update_bom_line(
    bom_id: uuid.UUID,
    line_id: uuid.UUID,
    body: BomLineUpdate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        line = (await db.execute(
            select(BomLine).where(and_(BomLine.org_id == org_id, BomLine.bom_id == bom_id, BomLine.id == line_id))
        )).scalar_one_or_none()
        if not line:
            raise HTTPException(status_code=404, detail="BOM line not found")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(line, field, value)
        await db.commit()
        await db.refresh(line)
        return _row(line)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"update_bom_line failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/manufacturing/boms/{bom_id}/lines/{line_id}", status_code=204)
async def delete_bom_line(
    bom_id: uuid.UUID,
    line_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        line = (await db.execute(
            select(BomLine).where(and_(BomLine.org_id == org_id, BomLine.bom_id == bom_id, BomLine.id == line_id))
        )).scalar_one_or_none()
        if not line:
            raise HTTPException(status_code=404, detail="BOM line not found")
        await db.delete(line)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"delete_bom_line failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Work Order endpoints ──────────────────────────────────────────────────────

@router.get("/api/manufacturing/work-orders")
async def list_work_orders(
    status: Optional[str] = None,
    bom_id: Optional[uuid.UUID] = None,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        q = select(WorkOrder).where(WorkOrder.org_id == org_id)
        if status:
            q = q.where(WorkOrder.status == status)
        if bom_id:
            q = q.where(WorkOrder.bom_id == bom_id)
        rows = (await db.execute(q.order_by(WorkOrder.created_at.desc()))).scalars().all()
        result = []
        for wo in rows:
            d = _row(wo)
            mat_lines = (await db.execute(
                select(WorkOrderMaterialLine).where(WorkOrderMaterialLine.work_order_id == wo.id)
            )).scalars().all()
            lab_lines = (await db.execute(
                select(WorkOrderLabourLine).where(WorkOrderLabourLine.work_order_id == wo.id)
            )).scalars().all()
            d["material_lines"] = [_row(l) for l in mat_lines]
            d["labour_lines"] = [_row(l) for l in lab_lines]
            result.append(d)
        return result
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_work_orders failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/manufacturing/work-orders", status_code=201)
async def create_work_order(
    body: WorkOrderCreate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        bom = (await db.execute(
            select(BomHeader).where(and_(BomHeader.org_id == org_id, BomHeader.id == body.bom_id))
        )).scalar_one_or_none()
        if not bom:
            raise HTTPException(status_code=404, detail="BOM not found")

        order_number = await _next_order_number(db, org_id)
        wo = WorkOrder(
            id=uuid.uuid4(),
            org_id=org_id,
            order_number=order_number,
            **body.model_dump(),
        )
        db.add(wo)
        await db.flush()

        # Auto-populate material lines from BOM
        bom_lines = (await db.execute(
            select(BomLine).where(BomLine.bom_id == bom.id)
        )).scalars().all()
        for bl in bom_lines:
            db.add(WorkOrderMaterialLine(
                id=uuid.uuid4(),
                org_id=org_id,
                work_order_id=wo.id,
                product_id=bl.component_product_id,
                planned_qty=bl.quantity * body.planned_qty,
                unit=bl.unit,
            ))

        await db.commit()
        await db.refresh(wo)
        d = _row(wo)
        mat_lines = (await db.execute(
            select(WorkOrderMaterialLine).where(WorkOrderMaterialLine.work_order_id == wo.id)
        )).scalars().all()
        d["material_lines"] = [_row(l) for l in mat_lines]
        d["labour_lines"] = []
        return d
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_work_order failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/manufacturing/work-orders/{wo_id}")
async def get_work_order(
    wo_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        wo = (await db.execute(
            select(WorkOrder).where(and_(WorkOrder.org_id == org_id, WorkOrder.id == wo_id))
        )).scalar_one_or_none()
        if not wo:
            raise HTTPException(status_code=404, detail="Work order not found")
        d = _row(wo)
        mat_lines = (await db.execute(
            select(WorkOrderMaterialLine).where(WorkOrderMaterialLine.work_order_id == wo_id)
        )).scalars().all()
        lab_lines = (await db.execute(
            select(WorkOrderLabourLine).where(WorkOrderLabourLine.work_order_id == wo_id)
        )).scalars().all()
        d["material_lines"] = [_row(l) for l in mat_lines]
        d["labour_lines"] = [_row(l) for l in lab_lines]
        return d
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"get_work_order failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/manufacturing/work-orders/{wo_id}")
async def update_work_order(
    wo_id: uuid.UUID,
    body: WorkOrderUpdate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        wo = (await db.execute(
            select(WorkOrder).where(and_(WorkOrder.org_id == org_id, WorkOrder.id == wo_id))
        )).scalar_one_or_none()
        if not wo:
            raise HTTPException(status_code=404, detail="Work order not found")
        if wo.status in ("completed", "cancelled"):
            raise HTTPException(status_code=422, detail="Cannot update a completed or cancelled work order")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(wo, field, value)
        await db.commit()
        await db.refresh(wo)
        return _row(wo)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"update_work_order failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/manufacturing/work-orders/{wo_id}/plan")
async def plan_work_order(
    wo_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """draft → planned. Runs feasibility check and rejects if any component is short."""
    user, member = auth
    org_id = member.org_id
    try:
        wo = (await db.execute(
            select(WorkOrder).where(and_(WorkOrder.org_id == org_id, WorkOrder.id == wo_id))
        )).scalar_one_or_none()
        if not wo:
            raise HTTPException(status_code=404, detail="Work order not found")
        if wo.status != "draft":
            raise HTTPException(status_code=422, detail="Only draft work orders can be planned")

        # Feasibility check
        mat_lines = (await db.execute(
            select(WorkOrderMaterialLine).where(WorkOrderMaterialLine.work_order_id == wo_id)
        )).scalars().all()

        shortfalls = []
        for line in mat_lines:
            sl = (await db.execute(
                select(StockLevel).where(
                    and_(
                        StockLevel.org_id == org_id,
                        StockLevel.product_id == line.product_id,
                        StockLevel.warehouse_id == wo.warehouse_id,
                    )
                )
            )).scalar_one_or_none()
            available = sl.quantity if sl else 0
            needed = int(line.planned_qty)
            if available < needed:
                product = (await db.execute(
                    select(Product).where(Product.id == line.product_id)
                )).scalar_one_or_none()
                shortfalls.append({
                    "product_id": str(line.product_id),
                    "name": product.name if product else "Unknown",
                    "needed": needed,
                    "available": available,
                    "short": needed - available,
                })

        if shortfalls:
            raise HTTPException(
                status_code=422,
                detail={"message": "Insufficient stock for planning", "shortfalls": shortfalls},
            )

        wo.status = "planned"
        await db.commit()
        await db.refresh(wo)
        return _row(wo)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"plan_work_order failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/manufacturing/work-orders/{wo_id}/start")
async def start_work_order(
    wo_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        wo = (await db.execute(
            select(WorkOrder).where(and_(WorkOrder.org_id == org_id, WorkOrder.id == wo_id))
        )).scalar_one_or_none()
        if not wo:
            raise HTTPException(status_code=404, detail="Work order not found")
        if wo.status != "planned":
            raise HTTPException(status_code=422, detail="Only planned work orders can be started")
        wo.status = "in_progress"
        wo.actual_start = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(wo)
        return _row(wo)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"start_work_order failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/manufacturing/work-orders/{wo_id}/complete")
async def complete_work_order(
    wo_id: uuid.UUID,
    body: WorkOrderComplete,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        wo = (await db.execute(
            select(WorkOrder).where(and_(WorkOrder.org_id == org_id, WorkOrder.id == wo_id))
        )).scalar_one_or_none()
        if not wo:
            raise HTTPException(status_code=404, detail="Work order not found")
        if wo.status != "in_progress":
            raise HTTPException(status_code=422, detail="Only in-progress work orders can be completed")

        # Load material lines before calling _complete_work_order
        mat_lines = (await db.execute(
            select(WorkOrderMaterialLine).where(WorkOrderMaterialLine.work_order_id == wo_id)
        )).scalars().all()
        wo.material_lines = list(mat_lines)

        movements = await _complete_work_order(db, wo, body.produced_qty, body.material_actuals, org_id)
        await db.commit()
        await db.refresh(wo)
        return {**_row(wo), "movements": movements}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"complete_work_order failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/manufacturing/work-orders/{wo_id}/cancel")
async def cancel_work_order(
    wo_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        wo = (await db.execute(
            select(WorkOrder).where(and_(WorkOrder.org_id == org_id, WorkOrder.id == wo_id))
        )).scalar_one_or_none()
        if not wo:
            raise HTTPException(status_code=404, detail="Work order not found")
        if wo.status in ("completed", "cancelled"):
            raise HTTPException(status_code=422, detail="Cannot cancel a completed or already cancelled work order")
        wo.status = "cancelled"
        await db.commit()
        await db.refresh(wo)
        return _row(wo)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"cancel_work_order failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/manufacturing/work-orders/{wo_id}/labour", status_code=201)
async def add_labour_line(
    wo_id: uuid.UUID,
    body: LabourLineCreate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        wo = (await db.execute(
            select(WorkOrder).where(and_(WorkOrder.org_id == org_id, WorkOrder.id == wo_id))
        )).scalar_one_or_none()
        if not wo:
            raise HTTPException(status_code=404, detail="Work order not found")
        line = WorkOrderLabourLine(id=uuid.uuid4(), org_id=org_id, work_order_id=wo_id, **body.model_dump())
        db.add(line)
        await db.commit()
        await db.refresh(line)
        return _row(line)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"add_labour_line failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/manufacturing/work-orders/{wo_id}/labour/{line_id}", status_code=204)
async def delete_labour_line(
    wo_id: uuid.UUID,
    line_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        line = (await db.execute(
            select(WorkOrderLabourLine).where(
                and_(WorkOrderLabourLine.org_id == org_id, WorkOrderLabourLine.work_order_id == wo_id, WorkOrderLabourLine.id == line_id)
            )
        )).scalar_one_or_none()
        if not line:
            raise HTTPException(status_code=404, detail="Labour line not found")
        await db.delete(line)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"delete_labour_line failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Planning / feasibility ────────────────────────────────────────────────────

@router.post("/api/manufacturing/planning/check")
async def check_feasibility(
    body: FeasibilityCheck,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Read-only stock feasibility check — no stock changes."""
    user, member = auth
    org_id = member.org_id
    try:
        bom = (await db.execute(
            select(BomHeader).where(and_(BomHeader.org_id == org_id, BomHeader.id == body.bom_id))
        )).scalar_one_or_none()
        if not bom:
            raise HTTPException(status_code=404, detail="BOM not found")

        bom_lines = (await db.execute(
            select(BomLine).where(BomLine.bom_id == bom.id)
        )).scalars().all()

        shortfalls = []
        for bl in bom_lines:
            needed = int(bl.quantity * body.qty)
            sl = (await db.execute(
                select(StockLevel).where(
                    and_(
                        StockLevel.org_id == org_id,
                        StockLevel.product_id == bl.component_product_id,
                        StockLevel.warehouse_id == body.warehouse_id,
                    )
                )
            )).scalar_one_or_none()
            available = sl.quantity if sl else 0
            product = (await db.execute(
                select(Product).where(Product.id == bl.component_product_id)
            )).scalar_one_or_none()
            shortfalls.append({
                "product_id": str(bl.component_product_id),
                "name": product.name if product else "Unknown",
                "sku": product.sku if product else "",
                "needed": needed,
                "available": available,
                "short": max(0, needed - available),
                "ok": available >= needed,
            })

        feasible = all(s["ok"] for s in shortfalls)
        return {"feasible": feasible, "shortfalls": shortfalls, "bom_id": str(body.bom_id), "qty": body.qty}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"check_feasibility failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Kits ──────────────────────────────────────────────────────────────────────

@router.get("/api/manufacturing/kits")
async def list_kits(
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        boms = (await db.execute(
            select(BomHeader).where(and_(BomHeader.org_id == org_id, BomHeader.is_kit == True))
            .order_by(BomHeader.name)
        )).scalars().all()
        result = []
        for b in boms:
            lines = (await db.execute(
                select(BomLine).where(BomLine.bom_id == b.id)
            )).scalars().all()
            d = _row(b)
            d["lines"] = [_row(l) for l in lines]
            result.append(d)
        return result
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_kits failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/manufacturing/kits", status_code=201)
async def create_kit(
    body: BomCreate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Create a BOM with is_kit=True."""
    user, member = auth
    org_id = member.org_id
    try:
        row = BomHeader(id=uuid.uuid4(), org_id=org_id, **{**body.model_dump(), "is_kit": True})
        db.add(row)
        await db.commit()
        await db.refresh(row)
        d = _row(row)
        d["lines"] = []
        return d
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_kit failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/manufacturing/kits/{bom_id}/build")
async def build_kit(
    bom_id: uuid.UUID,
    body: KitBuild,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Instantly assemble a kit: create + immediately complete a work order."""
    user, member = auth
    org_id = member.org_id
    try:
        bom = (await db.execute(
            select(BomHeader).where(
                and_(BomHeader.org_id == org_id, BomHeader.id == bom_id, BomHeader.is_kit == True)
            )
        )).scalar_one_or_none()
        if not bom:
            raise HTTPException(status_code=404, detail="Kit BOM not found")

        order_number = await _next_order_number(db, org_id)
        wo = WorkOrder(
            id=uuid.uuid4(),
            org_id=org_id,
            bom_id=bom_id,
            warehouse_id=body.warehouse_id,
            order_number=order_number,
            status="in_progress",
            planned_qty=body.qty,
            actual_start=datetime.now(timezone.utc),
        )
        db.add(wo)
        await db.flush()

        # Create material lines from BOM
        bom_lines = (await db.execute(
            select(BomLine).where(BomLine.bom_id == bom.id)
        )).scalars().all()
        mat_lines = []
        for bl in bom_lines:
            ml = WorkOrderMaterialLine(
                id=uuid.uuid4(),
                org_id=org_id,
                work_order_id=wo.id,
                product_id=bl.component_product_id,
                planned_qty=bl.quantity * body.qty,
                unit=bl.unit,
            )
            db.add(ml)
            mat_lines.append(ml)
        await db.flush()

        wo.material_lines = mat_lines
        movements = await _complete_work_order(db, wo, body.qty, None, org_id)
        await db.commit()
        return {"order_number": order_number, "produced_qty": body.qty, "movements": movements}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"build_kit failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
