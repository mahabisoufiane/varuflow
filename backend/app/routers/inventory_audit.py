"""Inventory audit trail router (Item 47) — PRO-gated.

Endpoints under ``/api/inventory/audit``:

* ``GET /movements``       — full movement history with filters
* ``GET /movements.csv``   — CSV export of the same filtered set
* ``GET /product/{id}``    — shortcut: all movements for one product
* ``GET /warehouse/{id}``  — shortcut: all movements for one warehouse

Every movement row is joined to its companion ``AuditLogEntry`` (via
the ``stock.movement`` action written in ``inventory.create_movement``
in the same transaction) so the response carries actor + IP metadata.
Unusual movements (large OUT, manual ADJUSTMENT) are flagged server-
side so the UI can highlight them without client-side thresholds.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_plan
from app.models.inventory import StockMovement, StockMovementType
from app.models.organization import OrgPlan
from app.services import inventory_audit_service as svc
from app.services.audit import fetch_audit_for_targets, log_action


router = APIRouter(
    prefix="/api/inventory/audit",
    tags=["inventory-audit"],
    # PRO-gated — the audit trail is a premium feature for compliance
    # and shrinkage investigation, not a basic inventory view.
    dependencies=[Depends(require_plan(OrgPlan.PRO))],
)


# ═══════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════


class MovementAuditOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    type: str
    quantity: int
    product_id: uuid.UUID
    product_sku: str | None
    product_name: str | None
    warehouse_id: uuid.UUID
    warehouse_name: str | None
    reference: str | None
    reason: str | None       # ``note`` — renamed for spec clarity.
    actor_user_id: uuid.UUID | None
    ip_address: str | None
    unusual: bool
    reasons: list[str]


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _actor(ctx: tuple):
    user, _ = ctx
    return user.get("user_id")


async def _query_movements(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    product_id: uuid.UUID | None,
    warehouse_id: uuid.UUID | None,
    movement_type: StockMovementType | None,
    actor_user_id: uuid.UUID | None,
    start_date: datetime | None,
    end_date: datetime | None,
    limit: int,
) -> list[tuple[StockMovement, dict]]:
    """Pull filtered stock movements + the matching audit-log row per
    movement so the caller renders actor + IP in one pass."""
    q = (
        select(StockMovement)
        .options(
            selectinload(StockMovement.product),
            selectinload(StockMovement.warehouse),
        )
        .where(StockMovement.org_id == org_id)
    )
    if product_id is not None:
        q = q.where(StockMovement.product_id == product_id)
    if warehouse_id is not None:
        q = q.where(StockMovement.warehouse_id == warehouse_id)
    if movement_type is not None:
        q = q.where(StockMovement.type == movement_type)
    if start_date is not None:
        q = q.where(StockMovement.created_at >= start_date)
    if end_date is not None:
        q = q.where(StockMovement.created_at <= end_date)

    # Sort newest-first so the UI shows fresh events without extra
    # sorting. Limit protects the backend from a "dump everything"
    # request for huge orgs.
    q = q.order_by(StockMovement.created_at.desc()).limit(limit)
    movements = (await db.execute(q)).scalars().all()

    # Single batched fetch to join audit-log entries.
    audits = await fetch_audit_for_targets(
        db,
        org_id=org_id,
        target_type="stock_movement",
        target_ids=[str(m.id) for m in movements],
    )

    # Apply the actor_user_id filter post-fetch — the audit join is
    # cheap (bounded by ``limit``) and this keeps the SQL simpler
    # than a LEFT JOIN + nullable filter in Alembic migrations.
    result: list[tuple[StockMovement, dict]] = []
    for m in movements:
        entry = audits.get(str(m.id))
        actor_id = getattr(entry, "actor_user_id", None) if entry else None
        ip = getattr(entry, "ip_address", None) if entry else None
        if actor_user_id is not None and actor_id != actor_user_id:
            continue
        result.append((m, {"actor_user_id": actor_id, "ip_address": ip}))
    return result


def _to_audit_out(m: StockMovement, extra: dict) -> MovementAuditOut:
    flag = svc.classify_movement(
        movement_type=m.type.value if hasattr(m.type, "value") else str(m.type),
        quantity=m.quantity,
        note=m.note,
    )
    product = getattr(m, "product", None)
    warehouse = getattr(m, "warehouse", None)
    return MovementAuditOut(
        id=m.id,
        created_at=m.created_at,
        type=m.type.value if hasattr(m.type, "value") else str(m.type),
        quantity=m.quantity,
        product_id=m.product_id,
        product_sku=getattr(product, "sku", None),
        product_name=getattr(product, "name", None),
        warehouse_id=m.warehouse_id,
        warehouse_name=getattr(warehouse, "name", None),
        reference=m.reference,
        reason=m.note,
        actor_user_id=extra.get("actor_user_id"),
        ip_address=extra.get("ip_address"),
        unusual=flag.unusual,
        reasons=list(flag.reasons),
    )


# ═══════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════


@router.get("/movements", response_model=list[MovementAuditOut])
async def list_movement_audit(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    product_id: uuid.UUID | None = Query(default=None),
    warehouse_id: uuid.UUID | None = Query(default=None),
    movement_type: StockMovementType | None = Query(default=None, alias="type"),
    actor_user_id: uuid.UUID | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
):
    org_id = _org(ctx)
    rows = await _query_movements(
        db, org_id=org_id,
        product_id=product_id, warehouse_id=warehouse_id,
        movement_type=movement_type, actor_user_id=actor_user_id,
        start_date=start_date, end_date=end_date,
        limit=limit,
    )
    return [_to_audit_out(m, extra) for m, extra in rows]


@router.get("/movements.csv")
async def export_movement_audit_csv(
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    product_id: uuid.UUID | None = Query(default=None),
    warehouse_id: uuid.UUID | None = Query(default=None),
    movement_type: StockMovementType | None = Query(default=None, alias="type"),
    actor_user_id: uuid.UUID | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
):
    """Export the filtered audit trail as CSV.

    Audit-logged because the export contains actor IPs and movement
    histories — exactly the kind of surface an auditor wants proof
    of downloading.
    """
    org_id = _org(ctx)
    rows = await _query_movements(
        db, org_id=org_id,
        product_id=product_id, warehouse_id=warehouse_id,
        movement_type=movement_type, actor_user_id=actor_user_id,
        start_date=start_date, end_date=end_date,
        limit=svc.EXPORT_ROW_CAP,
    )
    export_rows: list[svc.ExportRow] = []
    for m, extra in rows:
        flag = svc.classify_movement(
            movement_type=m.type.value if hasattr(m.type, "value") else str(m.type),
            quantity=m.quantity,
            note=m.note,
        )
        product = getattr(m, "product", None)
        warehouse = getattr(m, "warehouse", None)
        export_rows.append(
            svc.ExportRow(
                timestamp=m.created_at,
                type=m.type.value if hasattr(m.type, "value") else str(m.type),
                quantity=int(m.quantity),
                product_sku=getattr(product, "sku", "") or "",
                product_name=getattr(product, "name", "") or "",
                warehouse=getattr(warehouse, "name", "") or "",
                reference=m.reference,
                reason=m.note,
                actor_user_id=(
                    str(extra.get("actor_user_id"))
                    if extra.get("actor_user_id") else None
                ),
                ip_address=extra.get("ip_address"),
                unusual=flag.unusual,
            )
        )

    body = svc.render_csv(export_rows)
    await log_action(
        db,
        action="inventory_audit.exported",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="inventory_audit",
        target_id=str(org_id),
        request=request,
        extra={
            "rows": len(export_rows),
            "filters": {
                "product_id": str(product_id) if product_id else None,
                "warehouse_id": str(warehouse_id) if warehouse_id else None,
                "type": movement_type.value if movement_type else None,
                "actor_user_id": str(actor_user_id) if actor_user_id else None,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            },
        },
    )
    await db.commit()

    return Response(
        content=body,
        media_type="text/csv",
        headers={
            "Content-Disposition":
                'attachment; filename="inventory-audit.csv"',
        },
    )


@router.get("/product/{product_id}", response_model=list[MovementAuditOut])
async def list_product_audit(
    product_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=500, ge=1, le=2000),
):
    """All movements for one product. Tenant scoping enforced by
    ``_query_movements`` via ``org_id``."""
    org_id = _org(ctx)
    rows = await _query_movements(
        db, org_id=org_id,
        product_id=product_id, warehouse_id=None,
        movement_type=None, actor_user_id=None,
        start_date=None, end_date=None,
        limit=limit,
    )
    return [_to_audit_out(m, extra) for m, extra in rows]


@router.get("/warehouse/{warehouse_id}", response_model=list[MovementAuditOut])
async def list_warehouse_audit(
    warehouse_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=500, ge=1, le=2000),
):
    org_id = _org(ctx)
    rows = await _query_movements(
        db, org_id=org_id,
        product_id=None, warehouse_id=warehouse_id,
        movement_type=None, actor_user_id=None,
        start_date=None, end_date=None,
        limit=limit,
    )
    return [_to_audit_out(m, extra) for m, extra in rows]
