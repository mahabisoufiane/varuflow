"""Stock-transfer service (Item 38, v53).

Pure + DB-bound split (same style as Items 30–37). The pure layer
owns the state machine, quantity validation, and receipt arithmetic
— exhaustively unit-testable without a database. The DB layer owns
atomic updates to ``stock_levels`` and the insertion of
corresponding ``stock_movements`` rows.

Lifecycle:

    DRAFT  ──ship──►  IN_TRANSIT  ──receive──►  RECEIVED
      │                    │              └──partial──►  PARTIAL ──►(more receipts)──►  RECEIVED
      └──cancel──►  CANCELLED (from DRAFT only)

Notes on invariants the DB enforces (mirrored in pure helpers so a
call that would violate the DB constraint raises a typed error
*before* the SQL round-trip):

* ``qty_requested > 0`` — no zero-quantity lines.
* ``qty_shipped ≤ qty_requested`` — cannot ship more than asked.
* ``qty_received ≤ qty_shipped`` — cannot receive more than
  actually left the source warehouse.
* ``from_warehouse_id <> to_warehouse_id`` — intra-warehouse
  transfers are a no-op; force the caller to use stock adjustments
  instead.
"""
from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable


# ═══════════════════════════════════════════════════════════════════
# State machine (pure)
# ═══════════════════════════════════════════════════════════════════


class TransferStatus(str, enum.Enum):
    """Mirror of ``StockTransferStatus`` without the ORM dependency.

    Kept as a separate enum so the pure test sandbox doesn't need to
    import ``app.models`` (which is 3.9-incompatible). The router
    converts to / from the ORM enum at the boundary.
    """
    DRAFT = "DRAFT"
    IN_TRANSIT = "IN_TRANSIT"
    PARTIAL = "PARTIAL"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"


# Allowed transitions. The router invokes ``assert_can_transition``
# before flipping status; a violation raises ``ValueError`` with a
# coded message the router turns into a 409.
_ALLOWED = {
    TransferStatus.DRAFT: {TransferStatus.IN_TRANSIT, TransferStatus.CANCELLED},
    TransferStatus.IN_TRANSIT: {TransferStatus.PARTIAL, TransferStatus.RECEIVED},
    TransferStatus.PARTIAL: {TransferStatus.PARTIAL, TransferStatus.RECEIVED},
    TransferStatus.RECEIVED: set(),
    TransferStatus.CANCELLED: set(),
}


def assert_can_transition(
    current: TransferStatus, target: TransferStatus,
) -> None:
    """Raise ``ValueError`` if ``current`` → ``target`` is not allowed."""
    if target not in _ALLOWED[current]:
        raise ValueError(
            f"invalid_transition:{current.value}->{target.value}"
        )


def is_terminal(status: TransferStatus) -> bool:
    """Terminal states receive no further updates.

    ``RECEIVED`` and ``CANCELLED`` are both terminal — once there,
    the transfer is frozen. ``PARTIAL`` is *not* terminal because a
    follow-up receipt can still promote it to ``RECEIVED``.
    """
    return status in (TransferStatus.RECEIVED, TransferStatus.CANCELLED)


# ═══════════════════════════════════════════════════════════════════
# Line item validation (pure)
# ═══════════════════════════════════════════════════════════════════


@dataclass
class LineDraft:
    """Validated draft of a transfer line.

    Caller-facing input is a dict; the service normalises via
    :func:`parse_line_draft` so the DB write always receives clean
    values. Keeps the validation tree in one place.
    """
    product_id: uuid.UUID
    qty_requested: int
    batch_id: uuid.UUID | None = None


def parse_line_draft(raw: Any) -> LineDraft:
    """Coerce a mapping or object into a :class:`LineDraft`.

    Raises :class:`ValueError` for:

    * ``missing_product_id`` — no product key / attribute.
    * ``qty_must_be_positive`` — zero, negative, or non-numeric.
    * ``bad_uuid`` — product / batch id won't parse as UUID.
    """
    def _get(key):
        if isinstance(raw, dict):
            return raw.get(key)
        return getattr(raw, key, None)

    product_raw = _get("product_id")
    if product_raw is None:
        raise ValueError("missing_product_id")
    try:
        product_id = uuid.UUID(str(product_raw))
    except (TypeError, ValueError):
        raise ValueError("bad_uuid:product_id")

    qty_raw = _get("qty_requested") if _get("qty_requested") is not None else _get("qty")
    try:
        qty = int(qty_raw)
    except (TypeError, ValueError):
        raise ValueError("qty_must_be_positive")
    if qty <= 0:
        raise ValueError("qty_must_be_positive")

    batch_raw = _get("batch_id")
    batch_id = None
    if batch_raw is not None and batch_raw != "":
        try:
            batch_id = uuid.UUID(str(batch_raw))
        except (TypeError, ValueError):
            raise ValueError("bad_uuid:batch_id")

    return LineDraft(
        product_id=product_id,
        qty_requested=qty,
        batch_id=batch_id,
    )


def validate_transfer_draft(
    from_warehouse_id: uuid.UUID,
    to_warehouse_id: uuid.UUID,
    lines: Iterable[Any],
) -> list[LineDraft]:
    """Validate the warehouse pair and all lines in one pass.

    The router converts the ``ValueError`` into a 400; tests pin the
    exact error codes so downstream clients can branch on them.
    """
    if from_warehouse_id == to_warehouse_id:
        raise ValueError("same_warehouse_transfer")
    drafts = [parse_line_draft(raw) for raw in lines]
    if not drafts:
        raise ValueError("no_lines")
    # De-dupe: two lines for the same (product, batch) pair would make
    # the receipt accounting ambiguous. Merge them up-front so the
    # caller doesn't need to know this.
    merged: dict[tuple[uuid.UUID, uuid.UUID | None], LineDraft] = {}
    for d in drafts:
        key = (d.product_id, d.batch_id)
        if key in merged:
            merged[key].qty_requested += d.qty_requested
        else:
            merged[key] = d
    return list(merged.values())


# ═══════════════════════════════════════════════════════════════════
# Shipping + receipt arithmetic (pure)
# ═══════════════════════════════════════════════════════════════════


@dataclass
class LineView:
    """Pure view of a ``stock_transfer_items`` row for arithmetic.

    The DB-bound wrappers hydrate this from the ORM row before
    calling the pure calculators; the router + tests agree on the
    same shape.
    """
    product_id: uuid.UUID
    batch_id: uuid.UUID | None
    qty_requested: int
    qty_shipped: int = 0
    qty_received: int = 0


def compute_ship_quantities(
    lines: Iterable[LineView],
    overrides: dict[uuid.UUID, int] | None = None,
) -> dict[uuid.UUID, int]:
    """Return ``{product_id: qty_to_ship}`` after validating overrides.

    Ship endpoint semantics: absent a per-line override the shipped
    quantity defaults to ``qty_requested``. Overrides let the picker
    record "we could only pull 8 of the 10 requested" without having
    to edit the draft.

    Raises:

    * ``ship_qty_exceeds_requested`` — override > requested.
    * ``ship_qty_negative`` — override < 0.
    """
    out: dict[uuid.UUID, int] = {}
    ov = overrides or {}
    for line in lines:
        if line.product_id in ov:
            shipped = int(ov[line.product_id])
        else:
            shipped = int(line.qty_requested)
        if shipped < 0:
            raise ValueError("ship_qty_negative")
        if shipped > line.qty_requested:
            raise ValueError("ship_qty_exceeds_requested")
        out[line.product_id] = shipped
    return out


def compute_receive_quantities(
    lines: Iterable[LineView],
    received_now: dict[uuid.UUID, int],
) -> dict[uuid.UUID, int]:
    """Validate an incoming receipt batch and return ``{product_id: qty}``.

    ``received_now`` is the delta from this receive call; it is
    **added** to ``qty_received`` on the row. The caller uses this
    to stamp stock_movements for the destination warehouse.

    Raises:

    * ``unknown_line_for_receipt`` — a product id in ``received_now``
      is not part of the transfer.
    * ``receive_qty_negative`` — negative delta.
    * ``receive_qty_exceeds_shipped`` — cumulative received would
      overshoot what was actually shipped.
    """
    line_map = {line.product_id: line for line in lines}
    out: dict[uuid.UUID, int] = {}
    for pid, delta in received_now.items():
        if pid not in line_map:
            raise ValueError("unknown_line_for_receipt")
        delta_int = int(delta)
        if delta_int < 0:
            raise ValueError("receive_qty_negative")
        line = line_map[pid]
        new_total = line.qty_received + delta_int
        if new_total > line.qty_shipped:
            raise ValueError("receive_qty_exceeds_shipped")
        out[pid] = delta_int
    return out


def status_after_receipt(lines: Iterable[LineView]) -> TransferStatus:
    """Return the post-receipt status given line totals.

    If every line has ``qty_received == qty_shipped`` the transfer
    advances to ``RECEIVED``. Otherwise it sits at ``PARTIAL`` until
    a follow-up receipt closes the gap.
    """
    lines_list = list(lines)
    if not lines_list:
        return TransferStatus.RECEIVED
    all_done = all(
        line.qty_received == line.qty_shipped for line in lines_list
    )
    return TransferStatus.RECEIVED if all_done else TransferStatus.PARTIAL


# ═══════════════════════════════════════════════════════════════════
# History / filters (pure)
# ═══════════════════════════════════════════════════════════════════


@dataclass
class TransferSummary:
    id: uuid.UUID
    status: TransferStatus
    from_warehouse_id: uuid.UUID
    to_warehouse_id: uuid.UUID
    created_at: datetime
    line_count: int
    total_requested: int
    total_received: int


def summarise(
    transfer_id: uuid.UUID,
    status: TransferStatus,
    from_wh: uuid.UUID,
    to_wh: uuid.UUID,
    created_at: datetime,
    lines: Iterable[LineView],
) -> TransferSummary:
    lines_list = list(lines)
    return TransferSummary(
        id=transfer_id,
        status=status,
        from_warehouse_id=from_wh,
        to_warehouse_id=to_wh,
        created_at=created_at,
        line_count=len(lines_list),
        total_requested=sum(l.qty_requested for l in lines_list),
        total_received=sum(l.qty_received for l in lines_list),
    )


# ═══════════════════════════════════════════════════════════════════
# DB-bound wrappers (lazy-import models so pure tests skip them).
# ═══════════════════════════════════════════════════════════════════


async def load_warehouses(db, *, org_id: uuid.UUID, ids: list[uuid.UUID]):
    """Fetch warehouses for the org; caller verifies membership.

    Warehouses are loaded in a single round-trip so the router can
    check both endpoints (source + destination) belong to the org
    without two individual ``db.get`` calls.
    """
    from sqlalchemy import select

    from app.features.inventory.models import Warehouse

    if not ids:
        return []
    result = await db.execute(
        select(Warehouse).where(
            Warehouse.org_id == org_id,
            Warehouse.id.in_(ids),
        )
    )
    return list(result.scalars().all())


async def get_stock_level(db, *, product_id: uuid.UUID, warehouse_id: uuid.UUID):
    from sqlalchemy import select

    from app.features.inventory.models import StockLevel

    result = await db.execute(
        select(StockLevel).where(
            StockLevel.product_id == product_id,
            StockLevel.warehouse_id == warehouse_id,
        )
    )
    return result.scalar_one_or_none()


async def adjust_stock_level(
    db,
    *,
    org_id: uuid.UUID,
    product_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    delta: int,
):
    """Upsert a stock_levels row with ``delta`` applied.

    Negative deltas decrement; a decrement that would take the row
    below zero raises ``ValueError("insufficient_stock")`` so the
    router can 409 before any movement is recorded.

    Positive deltas create the row on demand — destination
    warehouses may never have seen this SKU before.
    """
    from app.features.inventory.models import StockLevel

    existing = await get_stock_level(
        db, product_id=product_id, warehouse_id=warehouse_id,
    )
    if existing is None:
        if delta < 0:
            raise ValueError("insufficient_stock")
        existing = StockLevel(
            org_id=org_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity=delta,
        )
        db.add(existing)
    else:
        new_qty = existing.quantity + delta
        if new_qty < 0:
            raise ValueError("insufficient_stock")
        existing.quantity = new_qty
    await db.flush()
    return existing


async def record_movement(
    db,
    *,
    org_id: uuid.UUID,
    product_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    quantity: int,
    movement_type,
    reference: str,
    batch_id: uuid.UUID | None = None,
):
    """Append a ``stock_movements`` ledger row for audit / FEFO.

    ``reference`` is a human-readable string embedded as-is in the
    row; the router passes the transfer id so the movement shows up
    when auditing the transfer downstream.
    """
    from app.features.inventory.models import StockMovement

    row = StockMovement(
        org_id=org_id,
        product_id=product_id,
        warehouse_id=warehouse_id,
        type=movement_type,
        quantity=quantity,
        reference=reference,
        batch_id=batch_id,
    )
    db.add(row)
    await db.flush()
    return row


async def load_transfer(db, *, transfer_id: uuid.UUID, org_id: uuid.UUID):
    """Fetch a transfer + eager-loaded items for the given org."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.features.inventory.stock_transfers_models import StockTransfer

    stmt = (
        select(StockTransfer)
        .options(selectinload(StockTransfer.items))
        .where(
            StockTransfer.id == transfer_id,
            StockTransfer.org_id == org_id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_transfers(
    db,
    *,
    org_id: uuid.UUID,
    status: TransferStatus | None = None,
    warehouse_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """List transfers for an org with optional filters.

    ``warehouse_id`` matches either source or destination — the
    warehouse-scoped inbox UI wants to see arrivals *and* shipments
    from the same list.
    """
    from sqlalchemy import or_, select
    from sqlalchemy.orm import selectinload

    from app.features.inventory.stock_transfers_models import StockTransfer, StockTransferStatus

    stmt = (
        select(StockTransfer)
        .options(selectinload(StockTransfer.items))
        .where(StockTransfer.org_id == org_id)
        .order_by(StockTransfer.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status is not None:
        stmt = stmt.where(
            StockTransfer.status == StockTransferStatus(status.value),
        )
    if warehouse_id is not None:
        stmt = stmt.where(
            or_(
                StockTransfer.from_warehouse_id == warehouse_id,
                StockTransfer.to_warehouse_id == warehouse_id,
            )
        )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def now_utc() -> datetime:
    """Single source of truth for "now" — swappable in tests."""
    return datetime.now(timezone.utc)
