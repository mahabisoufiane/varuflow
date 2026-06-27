"""Stock-transfer router (Item 38).

Exposes six endpoints under ``/api/stock-transfers``:

* ``GET  /``                   — list (optional ``status`` / ``warehouse_id`` filters).
* ``GET  /{transfer_id}``      — detail (+ items).
* ``POST /``                   — create a DRAFT transfer. ``log_action("stock_transfer.created")``.
* ``POST /{id}/ship``          — DRAFT → IN_TRANSIT; decrements source stock +
                                  writes OUT movements per line.
                                  ``log_action("stock_transfer.shipped")``.
* ``POST /{id}/receive``       — IN_TRANSIT / PARTIAL → RECEIVED or PARTIAL;
                                  increments destination stock + writes IN
                                  movements. ``log_action("stock_transfer.received")``.
* ``POST /{id}/cancel``        — DRAFT → CANCELLED (no stock impact).
                                  ``log_action("stock_transfer.cancelled")``.

All mutations call :func:`app.services.audit.log_action`. The service
layer (``stock_transfer_service``) owns the state-machine transitions
and quantity arithmetic; this router is thin and focused on
authentication, serialisation, and audit.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from .models import StockMovementType, Warehouse
from app.features.auth.organization import Organization
from .stock_transfers_models import (
    StockTransfer,
    StockTransferItem,
    StockTransferStatus,
)
from app.services import stock_transfer_service as svc
from app.services.audit import log_action
from app.services.email import (
    send_stock_transfer_received_email,
    send_stock_transfer_request_email,
)

log = logging.getLogger(__name__)
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/stock-transfers", tags=["stock-transfers"], dependencies=[Depends(require_module("inventory"))])


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _actor(ctx: tuple) -> uuid.UUID | None:
    user, _ = ctx
    uid = user.get("user_id")
    if isinstance(uid, uuid.UUID):
        return uid
    try:
        return uuid.UUID(str(uid))
    except Exception:
        return None


def _line_views(transfer: StockTransfer) -> list[svc.LineView]:
    """Hydrate the ORM items into the pure ``LineView`` shape.

    The pure arithmetic helpers only read these four fields; keeping the
    conversion local means the router is the only place that knows how
    the ORM row maps onto the pure view.
    """
    return [
        svc.LineView(
            product_id=item.product_id,
            batch_id=item.batch_id,
            qty_requested=item.qty_requested,
            qty_shipped=item.qty_shipped,
            qty_received=item.qty_received,
        )
        for item in transfer.items
    ]


async def _warehouse_names(
    db: AsyncSession, *, org_id: uuid.UUID, ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    rows = await db.execute(
        select(Warehouse.id, Warehouse.name).where(
            Warehouse.org_id == org_id, Warehouse.id.in_(ids),
        )
    )
    return {r.id: r.name for r in rows.all()}


# ═══════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════


class TransferLineIn(BaseModel):
    product_id: uuid.UUID
    qty_requested: int = Field(gt=0, le=1_000_000)
    batch_id: uuid.UUID | None = None


class TransferCreateIn(BaseModel):
    from_warehouse_id: uuid.UUID
    to_warehouse_id: uuid.UUID
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[TransferLineIn] = Field(min_length=1)


class ShipLineIn(BaseModel):
    """Optional per-product override. Absent products ship their full
    requested quantity."""
    product_id: uuid.UUID
    qty_shipped: int = Field(ge=0)


class TransferShipIn(BaseModel):
    lines: list[ShipLineIn] = Field(default_factory=list)


class ReceiveLineIn(BaseModel):
    product_id: uuid.UUID
    qty_received: int = Field(ge=0)


class TransferReceiveIn(BaseModel):
    lines: list[ReceiveLineIn] = Field(default_factory=list)


class TransferItemOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    batch_id: uuid.UUID | None
    qty_requested: int
    qty_shipped: int
    qty_received: int

    model_config = {"from_attributes": True}


class TransferOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    from_warehouse_id: uuid.UUID
    to_warehouse_id: uuid.UUID
    status: StockTransferStatus
    notes: str | None
    created_by: uuid.UUID | None
    created_at: datetime
    shipped_at: datetime | None
    received_at: datetime | None
    cancelled_at: datetime | None
    items: list[TransferItemOut]

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════


@router.get("", response_model=list[TransferOut])
async def list_transfers(
    status_filter: Optional[StockTransferStatus] = Query(None, alias="status"),
    warehouse_id: uuid.UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    svc_status = (
        svc.TransferStatus(status_filter.value) if status_filter is not None else None
    )
    rows = await svc.list_transfers(
        db,
        org_id=org_id,
        status=svc_status,
        warehouse_id=warehouse_id,
        limit=limit,
        offset=offset,
    )
    return rows


@router.get("/{transfer_id}", response_model=TransferOut)
async def get_transfer(
    transfer_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    row = await svc.load_transfer(db, transfer_id=transfer_id, org_id=org_id)
    if row is None:
        raise HTTPException(status_code=404, detail="transfer_not_found")
    return row


@router.post("", response_model=TransferOut, status_code=201)
async def create_transfer(
    body: TransferCreateIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)

    # Validate the draft in the pure layer first — a bad warehouse pair
    # or malformed line raises ``ValueError`` with a stable code the
    # client can branch on (``same_warehouse_transfer`` / ``no_lines`` /
    # ``qty_must_be_positive`` / ``missing_product_id`` / ``bad_uuid``).
    try:
        drafts = svc.validate_transfer_draft(
            body.from_warehouse_id,
            body.to_warehouse_id,
            [l.model_dump() for l in body.lines],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Both warehouses must belong to the caller's org.
    warehouses = await svc.load_warehouses(
        db, org_id=org_id, ids=[body.from_warehouse_id, body.to_warehouse_id],
    )
    if len(warehouses) != 2:
        raise HTTPException(status_code=404, detail="warehouse_not_found")
    wh_by_id = {w.id: w for w in warehouses}

    transfer = StockTransfer(
        id=uuid.uuid4(),
        org_id=org_id,
        from_warehouse_id=body.from_warehouse_id,
        to_warehouse_id=body.to_warehouse_id,
        status=StockTransferStatus.DRAFT,
        created_by=_actor(ctx),
        notes=body.notes,
    )
    db.add(transfer)
    await db.flush()

    for d in drafts:
        db.add(
            StockTransferItem(
                id=uuid.uuid4(),
                transfer_id=transfer.id,
                product_id=d.product_id,
                batch_id=d.batch_id,
                qty_requested=d.qty_requested,
                qty_shipped=0,
                qty_received=0,
            )
        )

    await log_action(
        db,
        action="stock_transfer.created",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="stock_transfer",
        target_id=str(transfer.id),
        request=request,
        extra={
            "from_warehouse_id": str(body.from_warehouse_id),
            "to_warehouse_id": str(body.to_warehouse_id),
            "line_count": len(drafts),
        },
    )

    # Best-effort notification. Send only if the destination warehouse
    # has a contactable address on the org (we use ``Organization.email``
    # as the fallback operator inbox). Failures never rollback the DB
    # write — the transfer is already committed logically.
    org = await db.get(Organization, org_id)
    dest_email = getattr(org, "email", None) if org else None
    if dest_email:
        try:
            await send_stock_transfer_request_email(
                to_email=dest_email,
                org_name=getattr(org, "name", "") or "",
                transfer_id=str(transfer.id),
                from_warehouse=wh_by_id[body.from_warehouse_id].name,
                to_warehouse=wh_by_id[body.to_warehouse_id].name,
                line_count=len(drafts),
            )
        except Exception as e:  # noqa: BLE001 — email never blocks commit
            log.warning("transfer_request_email_failed id=%s err=%s", transfer.id, e)

    await db.commit()
    return await svc.load_transfer(db, transfer_id=transfer.id, org_id=org_id)


@router.post("/{transfer_id}/ship", response_model=TransferOut)
async def ship_transfer(
    transfer_id: uuid.UUID,
    body: TransferShipIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    transfer = await svc.load_transfer(db, transfer_id=transfer_id, org_id=org_id)
    if transfer is None:
        raise HTTPException(status_code=404, detail="transfer_not_found")

    current = svc.TransferStatus(transfer.status.value)
    try:
        svc.assert_can_transition(current, svc.TransferStatus.IN_TRANSIT)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    lines = _line_views(transfer)
    overrides = {l.product_id: l.qty_shipped for l in body.lines}
    try:
        qty_by_product = svc.compute_ship_quantities(lines, overrides)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Apply to ORM items + decrement source stock. If ``adjust_stock_level``
    # raises ``insufficient_stock`` the router surfaces a 409 and the DB
    # rollback happens via the session teardown on the raised HTTPException.
    for item in transfer.items:
        shipped = qty_by_product.get(item.product_id, 0)
        if shipped == 0:
            continue
        try:
            await svc.adjust_stock_level(
                db,
                org_id=org_id,
                product_id=item.product_id,
                warehouse_id=transfer.from_warehouse_id,
                delta=-shipped,
            )
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
        await svc.record_movement(
            db,
            org_id=org_id,
            product_id=item.product_id,
            warehouse_id=transfer.from_warehouse_id,
            quantity=shipped,
            movement_type=StockMovementType.OUT,
            reference=f"transfer:{transfer.id}",
            batch_id=item.batch_id,
        )
        item.qty_shipped = shipped

    transfer.status = StockTransferStatus.IN_TRANSIT
    transfer.shipped_at = svc.now_utc()

    await log_action(
        db,
        action="stock_transfer.shipped",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="stock_transfer",
        target_id=str(transfer.id),
        request=request,
        extra={
            "total_shipped": sum(qty_by_product.values()),
            "line_count": len(transfer.items),
        },
    )
    await db.commit()
    return await svc.load_transfer(db, transfer_id=transfer.id, org_id=org_id)


@router.post("/{transfer_id}/receive", response_model=TransferOut)
async def receive_transfer(
    transfer_id: uuid.UUID,
    body: TransferReceiveIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    transfer = await svc.load_transfer(db, transfer_id=transfer_id, org_id=org_id)
    if transfer is None:
        raise HTTPException(status_code=404, detail="transfer_not_found")

    current = svc.TransferStatus(transfer.status.value)
    if current not in (svc.TransferStatus.IN_TRANSIT, svc.TransferStatus.PARTIAL):
        raise HTTPException(
            status_code=409,
            detail=f"invalid_transition:{current.value}->RECEIVED",
        )

    # Default to receiving the full outstanding shipped amount when the
    # caller passes no lines. This is the common case: "everything
    # arrived, book it all".
    if not body.lines:
        received_now = {
            item.product_id: item.qty_shipped - item.qty_received
            for item in transfer.items
            if item.qty_shipped - item.qty_received > 0
        }
    else:
        received_now = {l.product_id: l.qty_received for l in body.lines}

    lines = _line_views(transfer)
    try:
        deltas = svc.compute_receive_quantities(lines, received_now)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    for item in transfer.items:
        delta = deltas.get(item.product_id, 0)
        if delta == 0:
            continue
        await svc.adjust_stock_level(
            db,
            org_id=org_id,
            product_id=item.product_id,
            warehouse_id=transfer.to_warehouse_id,
            delta=+delta,
        )
        await svc.record_movement(
            db,
            org_id=org_id,
            product_id=item.product_id,
            warehouse_id=transfer.to_warehouse_id,
            quantity=delta,
            movement_type=StockMovementType.IN,
            reference=f"transfer:{transfer.id}",
            batch_id=item.batch_id,
        )
        item.qty_received = item.qty_received + delta

    # Recompute status from the now-updated line totals.
    new_lines = _line_views(transfer)
    new_status = svc.status_after_receipt(new_lines)
    transfer.status = StockTransferStatus(new_status.value)
    if new_status == svc.TransferStatus.RECEIVED:
        transfer.received_at = svc.now_utc()

    await log_action(
        db,
        action="stock_transfer.received",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="stock_transfer",
        target_id=str(transfer.id),
        request=request,
        extra={
            "status": new_status.value,
            "total_received_now": sum(deltas.values()),
        },
    )

    # Best-effort email to the source warehouse / org operator.
    org = await db.get(Organization, org_id)
    op_email = getattr(org, "email", None) if org else None
    if op_email:
        try:
            names = await _warehouse_names(
                db,
                org_id=org_id,
                ids=[transfer.from_warehouse_id, transfer.to_warehouse_id],
            )
            await send_stock_transfer_received_email(
                to_email=op_email,
                org_name=getattr(org, "name", "") or "",
                transfer_id=str(transfer.id),
                from_warehouse=names.get(transfer.from_warehouse_id, ""),
                to_warehouse=names.get(transfer.to_warehouse_id, ""),
                partial=new_status == svc.TransferStatus.PARTIAL,
            )
        except Exception as e:  # noqa: BLE001 — email never blocks commit
            log.warning("transfer_received_email_failed id=%s err=%s", transfer.id, e)

    await db.commit()
    return await svc.load_transfer(db, transfer_id=transfer.id, org_id=org_id)


@router.post("/{transfer_id}/cancel", response_model=TransferOut)
async def cancel_transfer(
    transfer_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    transfer = await svc.load_transfer(db, transfer_id=transfer_id, org_id=org_id)
    if transfer is None:
        raise HTTPException(status_code=404, detail="transfer_not_found")

    current = svc.TransferStatus(transfer.status.value)
    try:
        svc.assert_can_transition(current, svc.TransferStatus.CANCELLED)
    except ValueError as e:
        # Only DRAFT → CANCELLED is legal; everything else (including
        # ``IN_TRANSIT``) is a 409 so stock already in transit isn't
        # silently stranded outside the ledger.
        raise HTTPException(status_code=409, detail=str(e))

    transfer.status = StockTransferStatus.CANCELLED
    transfer.cancelled_at = svc.now_utc()

    await log_action(
        db,
        action="stock_transfer.cancelled",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="stock_transfer",
        target_id=str(transfer.id),
        request=request,
    )
    await db.commit()
    return await svc.load_transfer(db, transfer_id=transfer.id, org_id=org_id)
