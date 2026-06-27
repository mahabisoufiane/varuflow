"""Item 14 — Stock count processing service.

Given a ``StockCount`` row whose items have been persisted, walk every
item and — if ``counted_qty != expected_qty`` — append one
``ADJUSTMENT`` ``StockMovement`` against the same (org, product,
warehouse) with quantity = counted_qty. This mirrors the behaviour of
``POST /api/inventory/movements`` with type=ADJUSTMENT: the router-side
code sets ``StockLevel.quantity = body.quantity`` (an absolute reset
rather than a delta), so cycle counts reconcile in a single write per
row.

Never called outside the submit-flow. Every mutation is logged once by
the caller (the router) so this function intentionally has no audit
side-effects — it's pure stock-ledger work.
"""
from __future__ import annotations

import uuid
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.inventory.models import StockLevel, StockMovement, StockMovementType
from app.features.inventory.stock_count import StockCount, StockCountItem

STOCK_COUNT_REASON = "Stock count adjustment"


async def apply_stock_count(
    db: AsyncSession,
    count: StockCount,
) -> dict[str, int]:
    """Reconcile counted_qty against StockLevel for every item.

    Returns a summary ``{adjustments, matches, positive, negative}`` for
    the caller's audit payload.
    """
    items: Iterable[StockCountItem] = list(count.items)
    adjustments = matches = positive = negative = 0

    for item in items:
        variance = item.counted_qty - item.expected_qty
        item.variance_qty = variance

        if variance == 0:
            matches += 1
            continue

        adjustments += 1
        if variance > 0:
            positive += 1
        else:
            negative += 1

        # Upsert the matching StockLevel row. If the product was never
        # stocked in this warehouse we still record the count — a
        # physical presence for a ghost product row is a legitimate
        # correction, not an error.
        sl = await db.scalar(
            select(StockLevel)
            .where(
                StockLevel.product_id == item.product_id,
                StockLevel.warehouse_id == count.warehouse_id,
            )
            .with_for_update()
        )
        if sl is None:
            sl = StockLevel(
                id=uuid.uuid4(),
                org_id=count.org_id,
                product_id=item.product_id,
                warehouse_id=count.warehouse_id,
                quantity=0,
            )
            db.add(sl)
            await db.flush()

        # ADJUSTMENT is an absolute set, matching the semantics in
        # backend/app/routers/inventory.py::create_movement. Using the
        # counted value makes repeated applies idempotent — re-running
        # the same submission lands on the same final stock level.
        sl.quantity = item.counted_qty

        mv = StockMovement(
            id=uuid.uuid4(),
            org_id=count.org_id,
            product_id=item.product_id,
            warehouse_id=count.warehouse_id,
            type=StockMovementType.ADJUSTMENT,
            quantity=item.counted_qty,
            reference=f"STOCK-COUNT-{count.id}",
            note=STOCK_COUNT_REASON,
            batch_id=item.batch_id,
        )
        db.add(mv)

    await db.flush()
    return {
        "adjustments": adjustments,
        "matches": matches,
        "positive": positive,
        "negative": negative,
    }
