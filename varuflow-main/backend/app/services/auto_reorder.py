"""Auto-reorder service (v38 — Item 16).

Given an organisation, inspect every product that is below its reorder
level and create one draft ``PurchaseOrder`` per preferred supplier.
Draft POs go through the existing `purchase_orders` table and are
identical in shape to manually-created ones — nothing is sent to the
supplier automatically. The org owner is notified by email and must
approve each draft before the usual SEND → RECEIVED lifecycle runs.

This is invoked from three places:

* ``_auto_reorder_check`` in the scheduler (daily sweep).
* ``POST /api/auto-reorder/run`` for the manual owner trigger.
* ``GET /api/auto-reorder/preview`` runs the same math but skips the
  DB writes entirely (dry-run).

Errors per-product never abort the whole run — we collect them and
mark the run status ``partial`` so the owner still receives POs for
products that did resolve cleanly.
"""
from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.inventory.auto_reorder_models import AutoReorderRun
from app.features.inventory.models import (
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    StockLevel,
    StockMovement,
    StockMovementType,
    Supplier,
)
from app.features.auth.organization import Organization
from app.services.audit import log_action

logger = logging.getLogger(__name__)

# Graceful fallback when a supplier has neither contracted nor observed
# lead time yet. Fourteen days mirrors the default the Item 18 spec
# recommends for the supplier onboarding UX.
_DEFAULT_LEAD_DAYS = 14


@dataclass
class PurchaseOrderSummary:
    """Lightweight view of a freshly-created draft PO returned from a run."""

    po_id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str
    items_count: int
    total_sek: Decimal


@dataclass
class PreviewLine:
    """One row of the dry-run preview — never persisted."""

    product_id: uuid.UUID
    product_name: str
    sku: str
    current_stock: int
    reorder_level: int
    suggested_qty: int
    preferred_supplier_id: uuid.UUID | None
    preferred_supplier_name: str | None
    estimated_cost_sek: Decimal


@dataclass
class AutoReorderResult:
    products_checked: int = 0
    purchase_orders_created: int = 0
    products_skipped: int = 0
    pos_created: list[PurchaseOrderSummary] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _lead_days(supplier: Supplier) -> int:
    """Resolve the lead time we should plan against for this supplier.

    Prefer the rolling-observed mean (``average_lead_days``) because it
    reflects reality; fall back to the contracted ``default_lead_days``
    if no POs have been received yet; last-resort fallback is 14 days.
    """
    if supplier.average_lead_days is not None:
        return max(1, int(math.ceil(float(supplier.average_lead_days))))
    if supplier.default_lead_days is not None:
        return max(1, int(supplier.default_lead_days))
    return _DEFAULT_LEAD_DAYS


async def _load_product_stock_map(
    db: AsyncSession, org_id: uuid.UUID
) -> dict[uuid.UUID, int]:
    """Sum stock across all warehouses for every product in the org.

    Loaded once per run to avoid N+1 lookups inside the main loop.
    """
    rows = await db.execute(
        select(
            StockLevel.product_id,
            func.coalesce(func.sum(StockLevel.quantity), 0).label("qty"),
        )
        .where(StockLevel.org_id == org_id)
        .group_by(StockLevel.product_id)
    )
    return {r.product_id: int(r.qty) for r in rows.all()}


async def _avg_daily_consumption(
    db: AsyncSession, org_id: uuid.UUID
) -> dict[uuid.UUID, float]:
    """Last-30-day OUT consumption per product, averaged to daily units.

    Returns {product_id: avg_daily_units}. Products with no OUT
    movements in the window are absent from the map — callers must
    treat them as zero.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    rows = await db.execute(
        select(
            StockMovement.product_id,
            func.coalesce(func.sum(StockMovement.quantity), 0).label("qty"),
        )
        .where(
            StockMovement.org_id == org_id,
            StockMovement.type == StockMovementType.OUT,
            StockMovement.created_at >= cutoff,
        )
        .group_by(StockMovement.product_id)
    )
    return {r.product_id: float(r.qty) / 30.0 for r in rows.all()}


def _suggest_qty(
    product: Product,
    current_stock: int,
    supplier: Supplier,
    avg_daily: float,
) -> int:
    """Apply the reorder-quantity formula from the Item 16 spec.

    If the owner pinned ``reorder_quantity`` on the product, honour it
    verbatim. Otherwise: ``max(reorder_level * 2 - current, ceil(avg *
    (lead + buffer)))`` with a floor of 1 — never order zero units of
    something the system has already flagged as below reorder level.
    """
    if product.reorder_quantity is not None and product.reorder_quantity > 0:
        return max(1, int(product.reorder_quantity))

    lead = _lead_days(supplier)
    buffer = max(0, int(product.reorder_lead_buffer_days or 0))
    consumption_qty = int(math.ceil(avg_daily * (lead + buffer)))
    gap_qty = (int(product.reorder_level) * 2) - int(current_stock)
    return max(1, max(consumption_qty, gap_qty))


async def _fetch_eligible_products(
    db: AsyncSession, org_id: uuid.UUID
) -> list[tuple[Product, int]]:
    """Products whose summed stock is at or below ``reorder_level``.

    Returns (product, total_stock) pairs. Excludes inactive products
    and products without reorder_level > 0 — a product with reorder
    level 0 is a signal that the owner doesn't want stock alerts for
    it, so we shouldn't auto-reorder it either.
    """
    rows = await db.execute(
        select(
            Product,
            func.coalesce(func.sum(StockLevel.quantity), 0).label("total_stock"),
        )
        .outerjoin(StockLevel, StockLevel.product_id == Product.id)
        .where(
            Product.org_id == org_id,
            Product.is_active == True,  # noqa: E712
            Product.reorder_level > 0,
        )
        .group_by(Product.id)
        .having(
            func.coalesce(func.sum(StockLevel.quantity), 0) <= Product.reorder_level
        )
    )
    return [(row[0], int(row[1])) for row in rows.all()]


async def preview_auto_reorder(
    db: AsyncSession, org_id: uuid.UUID
) -> list[PreviewLine]:
    """Dry-run: compute what *would* be ordered without creating anything."""
    products = await _fetch_eligible_products(db, org_id)
    if not products:
        return []

    supplier_ids = {
        p.preferred_supplier_id for p, _ in products if p.preferred_supplier_id
    }
    suppliers: dict[uuid.UUID, Supplier] = {}
    if supplier_ids:
        sup_rows = await db.execute(
            select(Supplier).where(Supplier.id.in_(supplier_ids))
        )
        suppliers = {s.id: s for s in sup_rows.scalars().all()}
    avg_daily_map = await _avg_daily_consumption(db, org_id)

    out: list[PreviewLine] = []
    for product, total_stock in products:
        supplier = (
            suppliers.get(product.preferred_supplier_id)
            if product.preferred_supplier_id
            else None
        )
        avg_daily = avg_daily_map.get(product.id, 0.0)
        if supplier is not None:
            qty = _suggest_qty(product, total_stock, supplier, avg_daily)
        else:
            # Still surface the product so the owner knows it would be
            # skipped — they typically fix the missing supplier link
            # straight from this screen.
            qty = 0
        out.append(
            PreviewLine(
                product_id=product.id,
                product_name=product.name,
                sku=product.sku,
                current_stock=total_stock,
                reorder_level=int(product.reorder_level),
                suggested_qty=qty,
                preferred_supplier_id=product.preferred_supplier_id,
                preferred_supplier_name=supplier.name if supplier else None,
                estimated_cost_sek=(Decimal(qty) * product.purchase_price)
                if qty
                else Decimal("0.00"),
            )
        )
    return out


async def run_auto_reorder(
    org_id: uuid.UUID,
    db: AsyncSession,
    triggered_by: str = "scheduler",
) -> AutoReorderResult:
    """Main entrypoint. Creates draft POs grouped by preferred supplier.

    Parameters
    ----------
    org_id : The organisation to run for. Caller has already verified
        membership / ownership — this function does NOT re-check.
    db : Open AsyncSession. Commits happen inside.
    triggered_by : "scheduler" | "manual" | "api" — recorded verbatim
        on the AutoReorderRun row.
    """
    result = AutoReorderResult()

    org = await db.get(Organization, org_id)
    if org is None or not org.is_active:
        result.errors.append("organization_not_found_or_inactive")
        await _record_run(db, org_id, triggered_by, result, status="failed")
        return result

    if not org.auto_reorder_enabled:
        # Called explicitly via manual trigger but the org switch is
        # off — record for the audit trail and bail cleanly.
        logger.info("auto_reorder skipped — disabled for org %s", org_id)
        await _record_run(db, org_id, triggered_by, result, status="completed")
        return result

    try:
        eligible = await _fetch_eligible_products(db, org_id)
    except Exception as exc:  # noqa: BLE001 — record & swallow per spec
        logger.exception("auto_reorder eligibility query failed org=%s", org_id)
        result.errors.append(f"eligibility_query_failed: {exc!r}")
        await _record_run(db, org_id, triggered_by, result, status="failed", error_message=str(exc))
        return result

    result.products_checked = len(eligible)
    if not eligible:
        await _record_run(db, org_id, triggered_by, result, status="completed")
        return result

    # Pre-load suppliers and consumption map in bulk so the main loop
    # never touches the DB for things it could know up front.
    supplier_ids = {
        p.preferred_supplier_id for p, _ in eligible if p.preferred_supplier_id
    }
    suppliers: dict[uuid.UUID, Supplier] = {}
    if supplier_ids:
        sup_rows = await db.execute(
            select(Supplier).where(
                Supplier.id.in_(supplier_ids),
                Supplier.org_id == org_id,
            )
        )
        suppliers = {s.id: s for s in sup_rows.scalars().all()}
    avg_daily_map = await _avg_daily_consumption(db, org_id)

    # Group (product, qty, supplier) by supplier_id
    by_supplier: dict[uuid.UUID, list[tuple[Product, int]]] = {}
    for product, total_stock in eligible:
        if not product.auto_reorder_enabled or product.preferred_supplier_id is None:
            result.products_skipped += 1
            continue
        supplier = suppliers.get(product.preferred_supplier_id)
        if supplier is None or not supplier.is_active:
            result.products_skipped += 1
            continue
        avg_daily = avg_daily_map.get(product.id, 0.0)
        qty = _suggest_qty(product, total_stock, supplier, avg_daily)
        by_supplier.setdefault(supplier.id, []).append((product, qty))

    had_failures = False
    for supplier_id, lines in by_supplier.items():
        supplier = suppliers[supplier_id]
        try:
            summary = await _create_draft_po(
                db, org_id=org_id, supplier=supplier, lines=lines
            )
        except Exception as exc:  # noqa: BLE001 — isolate per-supplier failures
            logger.exception(
                "auto_reorder PO creation failed org=%s supplier=%s",
                org_id, supplier_id,
            )
            result.errors.append(f"po_failed_{supplier_id}: {exc!r}")
            had_failures = True
            continue
        result.pos_created.append(summary)
        result.purchase_orders_created += 1

    run_status = "completed"
    if had_failures and result.purchase_orders_created == 0:
        run_status = "failed"
    elif had_failures:
        run_status = "partial"
    await _record_run(
        db,
        org_id,
        triggered_by,
        result,
        status=run_status,
        error_message="; ".join(result.errors) if result.errors else None,
    )

    if result.purchase_orders_created > 0:
        # Import at call-site to sidestep the email → scheduler → email
        # dependency loop at module load.
        from app.services.email import send_auto_reorder_notification_email

        notify_email = org.auto_reorder_notify_email
        if not notify_email:
            # Fall back to the owner's email — same resolution as the
            # existing low-stock email job.
            from app.services.scheduler import _org_notification_email as _resolve

            notify_email = await _resolve(db, org_id)
        if notify_email:
            try:
                await send_auto_reorder_notification_email(
                    to_email=notify_email,
                    org_name=org.name,
                    pos=[
                        {
                            "po_id": str(s.po_id),
                            "supplier_name": s.supplier_name,
                            "items_count": s.items_count,
                            "total_sek": f"{s.total_sek:,.2f}",
                        }
                        for s in result.pos_created
                    ],
                )
            except Exception:  # noqa: BLE001 — email failure must not void POs
                logger.exception(
                    "auto_reorder notification email failed org=%s", org_id
                )

    return result


async def _create_draft_po(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    supplier: Supplier,
    lines: list[tuple[Product, int]],
) -> PurchaseOrderSummary:
    """Insert one DRAFT PurchaseOrder + items for a supplier group.

    Mirrors ``POST /api/inventory/purchase-orders`` — same table, same
    status, same total calculation. Items are priced at the product's
    current ``purchase_price``; the owner can edit before approving.
    """
    lead = _lead_days(supplier)
    # Use the first product's buffer as representative — all lines
    # within a supplier group share one supplier and are reviewed by
    # the owner before SEND anyway, so aggregating buffer is fine.
    buffer = max(0, int(lines[0][0].reorder_lead_buffer_days or 0))
    expected_delivery = (datetime.now(timezone.utc) + timedelta(days=lead + buffer)).date()

    po = PurchaseOrder(
        org_id=org_id,
        supplier_id=supplier.id,
        status=PurchaseOrderStatus.DRAFT,
        notes=(
            "Auto-generated by Varuflow auto-reorder. "
            f"Expected delivery: {expected_delivery.isoformat()}."
        ),
    )
    db.add(po)
    await db.flush()

    total = Decimal("0.00")
    for product, qty in lines:
        unit_price = Decimal(str(product.purchase_price))
        line_total = (unit_price * qty).quantize(Decimal("0.01"))
        total += line_total
        db.add(
            PurchaseOrderItem(
                purchase_order_id=po.id,
                product_id=product.id,
                quantity=int(qty),
                unit_price=unit_price,
                line_total=line_total,
            )
        )
    po.total = total

    await log_action(
        db,
        action="purchase_order.auto_created",
        org_id=org_id,
        actor_user_id=None,  # scheduler/system
        target_type="purchase_order",
        target_id=str(po.id),
        extra={
            "supplier_id": str(supplier.id),
            "items_count": len(lines),
            "total_sek": str(total),
            "expected_delivery": expected_delivery.isoformat(),
        },
    )
    await db.commit()

    return PurchaseOrderSummary(
        po_id=po.id,
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        items_count=len(lines),
        total_sek=total,
    )


async def _record_run(
    db: AsyncSession,
    org_id: uuid.UUID,
    triggered_by: str,
    result: AutoReorderResult,
    *,
    status: str = "completed",
    error_message: str | None = None,
) -> None:
    """Insert one AutoReorderRun row. Never raises — telemetry only."""
    try:
        row = AutoReorderRun(
            org_id=org_id,
            triggered_by=triggered_by,
            products_checked=result.products_checked,
            purchase_orders_created=result.purchase_orders_created,
            products_skipped=result.products_skipped,
            status=status,
            error_message=error_message,
        )
        db.add(row)
        await db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("auto_reorder run-record insert failed org=%s", org_id)
        try:
            await db.rollback()
        except Exception:
            pass
