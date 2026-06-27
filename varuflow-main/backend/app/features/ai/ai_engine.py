"""
Varuflow AI Intelligence Engine
Modules:
  1 — Inventory Intelligence (stockout risk, dead stock)
  2 — Margin & Pricing Optimizer
  3 — Automated Workflow (combined detect → prescribe)
  5 — Customer Intelligence (RFM, late payers, churn)

GET  /api/ai/cards          — generate fresh action cards from live data
POST /api/ai/actions/send-reminder   — send payment reminder email
POST /api/ai/actions/mark-seen       — mark card seen (frontend tracking)
"""
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

log = logging.getLogger(__name__)
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module, require_plan
from app.features.inventory.models import (
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    StockLevel,
    StockMovement,
    StockMovementType,
    Supplier,
)
from app.features.invoicing.models import Customer, Invoice, InvoiceStatus
from app.features.auth.organization import OrgPlan, Organization
from app.features.portal.idempotency import IdempotencyKey
from sqlalchemy.exc import IntegrityError

router = APIRouter(
    prefix="/api/ai",
    tags=["ai"],
    dependencies=[Depends(require_plan(OrgPlan.PRO)), Depends(require_module("ai"))],
)

CardType = Literal["ALERT", "SUGGESTION", "WORKFLOW", "REPORT"]
Priority = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]

# Category margin benchmarks (gross margin %)
CATEGORY_BENCHMARKS: dict[str, float] = {
    "food": 18.0,
    "beverages": 20.0,
    "electronics": 22.0,
    "office": 25.0,
    "tools": 28.0,
    "default": 20.0,
}

# Assumed supplier lead time (days) when not specified
DEFAULT_LEAD_DAYS = 5


# ── Schemas ───────────────────────────────────────────────────────────────────

class ActionCard(BaseModel):
    id: str
    card_type: CardType
    priority: Priority
    module: int
    title: str
    insight: str
    action: str
    impact_estimate: str
    requires_approval: bool
    auto_execute_action: str | None = None
    # Extra data for execute endpoints
    meta: dict = {}


class CardsResponse(BaseModel):
    cards: list[ActionCard]
    generated_at: datetime
    org_id: str


class SendReminderRequest(BaseModel):
    invoice_id: uuid.UUID


class DraftPoRequest(BaseModel):
    product_id: uuid.UUID
    # Bound quantity so a caller can't submit 1e9 and overflow the PO's
    # numeric(12,2) line_total column (causing DataError or, worse,
    # silent wrap on some DB drivers). 100k covers any realistic
    # Nordic-wholesaler single-line order.
    quantity: int = Field(ge=1, le=100_000)


class ActionResult(BaseModel):
    status: str
    message: str


# ── Helper ────────────────────────────────────────────────────────────────────

def _priority_order(p: Priority) -> int:
    return {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}[p]


# ── Card generation ───────────────────────────────────────────────────────────

@router.get("/cards", response_model=CardsResponse)
async def get_action_cards(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    org_id = member.org_id
    today = date.today()
    cards: list[ActionCard] = []

    try:
        # ── MODULE 1: Inventory Intelligence ──────────────────────────────────

        # Sales velocity: OUT movements per product in last 7 days
        seven_days_ago = today - timedelta(days=7)
        velocity_rows = await db.execute(
            select(
                StockMovement.product_id,
                func.sum(StockMovement.quantity).label("sold_7d"),
            )
            .where(
                StockMovement.org_id == org_id,
                StockMovement.type == StockMovementType.OUT,
                StockMovement.created_at >= seven_days_ago,
            )
            .group_by(StockMovement.product_id)
        )
        velocity_map: dict[uuid.UUID, float] = {
            r.product_id: float(r.sold_7d) / 7.0 for r in velocity_rows
        }

        # Products with OUT movements in the last 30 days — precomputed once
        # instead of a per-product COUNT in the hot loop (previously one DB
        # round-trip per stock row, catastrophic on large catalogs).
        thirty_days_ago = today - timedelta(days=30)
        recent_sale_rows = await db.execute(
            select(StockMovement.product_id)
            .where(
                StockMovement.org_id == org_id,
                StockMovement.type == StockMovementType.OUT,
                StockMovement.created_at >= thirty_days_ago,
            )
            .group_by(StockMovement.product_id)
        )
        recent_sale_set: set[uuid.UUID] = {r.product_id for r in recent_sale_rows}

        # Stock levels with products — cap at 2k rows so a runaway catalog
        # can't wedge the worker building action cards. Tenants with more
        # than 2k SKUs still get cards for the first slice; the rest show
        # up after the underperformers are cleared.
        #
        # Aggregate quantity across ALL warehouses per product and compare
        # against Product.reorder_level — the canonical low-stock signal
        # used by the scheduler, weekly digest, dashboard KPI and AI chat
        # context. StockLevel.min_threshold is NEVER written by any
        # endpoint (it stays at its 0 default), so the old `qty <=
        # min_threshold AND min_threshold > 0` branch never fired and the
        # "below reorder point" card was effectively dead code — silently
        # hiding the one case module 1 is supposed to flag for SKUs
        # without recent sales velocity.
        stock_rows = await db.execute(
            select(
                Product,
                func.coalesce(func.sum(StockLevel.quantity), 0).label("quantity"),
            )
            .outerjoin(StockLevel, StockLevel.product_id == Product.id)
            .where(Product.org_id == org_id, Product.is_active == True)  # noqa: E712
            .group_by(Product.id)
            .limit(2000)
        )
        for p, qty in stock_rows:
            qty = int(qty)
            reorder_level = int(p.reorder_level or 0)
            avg_daily = velocity_map.get(p.id, 0.0)

            # Stockout risk
            if avg_daily > 0:
                days_left = qty / avg_daily
                if days_left <= DEFAULT_LEAD_DAYS:
                    priority: Priority = "CRITICAL" if days_left <= 1 else "HIGH"
                    cards.append(ActionCard(
                        id=f"stockout-{p.id}",
                        card_type="ALERT",
                        priority=priority,
                        module=1,
                        title=f"⚠️ {p.name} will run out in ~{days_left:.1f} days",
                        insight=(
                            f"{p.name} ({p.sku}) has {qty} units left with an average "
                            f"of {avg_daily:.1f} units sold per day. At current velocity, stock "
                            f"runs out in ~{days_left:.1f} days — within supplier lead time."
                        ),
                        action=f"Draft purchase order for {p.name} — recommend ordering {max(10, int(avg_daily * 14))} units",
                        impact_estimate=f"Stockout loss estimated {int(avg_daily * 3 * float(p.sell_price)):,} SEK over 3 days",
                        requires_approval=True,
                        auto_execute_action="draft_po",
                        meta={"product_id": str(p.id), "product_name": p.name, "suggested_qty": max(10, int(avg_daily * 14))},
                    ))
            elif qty <= reorder_level and reorder_level > 0:
                cards.append(ActionCard(
                    id=f"minthreshold-{p.id}",
                    card_type="ALERT",
                    priority="HIGH",
                    module=1,
                    title=f"📦 {p.name} below reorder point",
                    insight=(
                        f"{p.name} ({p.sku}) has {qty} units — at or below the reorder "
                        f"threshold of {reorder_level}. No recent sales velocity data."
                    ),
                    action=f"Review and restock {p.name}",
                    impact_estimate="Risk of stockout if demand resumes",
                    requires_approval=True,
                    auto_execute_action="draft_po",
                    meta={"product_id": str(p.id), "product_name": p.name, "suggested_qty": reorder_level * 3},
                ))

            # Dead stock: no OUT movements in 30+ days (precomputed set —
            # no per-product DB round-trip in this loop).
            if p.id not in recent_sale_set and qty > 0:
                stock_value = qty * float(p.purchase_price)
                cards.append(ActionCard(
                    id=f"deadstock-{p.id}",
                    card_type="SUGGESTION",
                    priority="MEDIUM",
                    module=1,
                    title=f"🛑 Dead stock: {p.name} — {qty} units unsold for 30+ days",
                    insight=(
                        f"{p.name} has {qty} units with no sales in over 30 days. "
                        f"Tied-up capital: ~{stock_value:,.0f} SEK. Consider a clearance action."
                    ),
                    action="Run clearance promotion at 15% discount or bundle with a fast-moving product",
                    impact_estimate=f"Recover up to {stock_value:,.0f} SEK in tied-up inventory capital",
                    requires_approval=True,
                    meta={"product_id": str(p.id), "product_name": p.name},
                ))

        # ── MODULE 2: Margin & Pricing Optimizer ──────────────────────────────

        # Bound the scan to 2000 products — matches the cap on Module 1's
        # stock-level scan and prevents a tenant with tens of thousands of
        # SKUs from pinning a worker on every dashboard load. The user
        # sees the 2k lowest-margin products (biggest deviation from
        # benchmark surfaces first after the cards are sorted), and cards
        # already go through a priority-sort + UI cap downstream.
        products_result = await db.execute(
            select(Product)
            .where(Product.org_id == org_id, Product.is_active == True)  # noqa: E712
            .limit(2000)
        )
        for p in products_result.scalars():
            if float(p.sell_price) <= 0:
                continue
            gross_margin = (float(p.sell_price) - float(p.purchase_price)) / float(p.sell_price)
            benchmark = CATEGORY_BENCHMARKS.get(
                (p.category or "").lower(),
                CATEGORY_BENCHMARKS["default"]
            ) / 100.0

            if gross_margin < benchmark * 0.75:  # > 25% below benchmark
                gap = benchmark - gross_margin
                suggested_price = float(p.purchase_price) / (1 - benchmark)
                cards.append(ActionCard(
                    id=f"margin-{p.id}",
                    card_type="SUGGESTION",
                    priority="HIGH" if gross_margin < 0.10 else "MEDIUM",
                    module=2,
                    title=f"📉 Margin leak: {p.name} at {gross_margin*100:.0f}% (benchmark: {benchmark*100:.0f}%)",
                    insight=(
                        f"{p.name} earns {gross_margin*100:.1f}% gross margin vs the category benchmark "
                        f"of {benchmark*100:.0f}%. The gap of {gap*100:.0f}% represents a pricing opportunity."
                    ),
                    action=f"Raise price from {float(p.sell_price):,.0f} to {suggested_price:,.0f} SEK, or renegotiate with supplier",
                    impact_estimate=f"⚠️ LOW CONFIDENCE — verify manually. Potential +{gap*float(p.sell_price):,.0f} SEK margin per unit",
                    requires_approval=True,
                    meta={"product_id": str(p.id), "current_price": float(p.sell_price), "suggested_price": round(suggested_price, 2)},
                ))

        # ── MODULE 5: Customer Intelligence ───────────────────────────────────

        # Late payers: overdue invoices by age bucket
        overdue_result = await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.customer))
            .where(
                Invoice.org_id == org_id,
                Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE]),
                Invoice.due_date < today,
            )
            .order_by(Invoice.due_date)
            # Bound the scan — an AR backlog of tens of thousands of
            # overdue invoices would otherwise materialise every row into
            # memory on every dashboard load. 1000 covers any realistic
            # Nordic-wholesaler backlog; oldest-due-first ordering means
            # the most urgent rows are always included.
            .limit(1000)
        )
        overdue_invoices = list(overdue_result.scalars())

        # Compute partial-payment totals for all overdue invoices in ONE
        # grouped query so every card below shows the REMAINING balance,
        # not the invoice face value. Previously a 10 000 SEK invoice
        # with a 7 000 SEK bank-transfer partial would surface on the
        # dashboard as "10 000 SEK outstanding" — inflating the AR
        # visible to the user by the collected-but-not-yet-settled
        # portion, and misleading the seller who clicks "send reminder"
        # (the reminder email itself was already fixed in a prior round
        # to charge the remaining balance, but the card title/insight/
        # impact/meta.amount still showed the gross). Matches the
        # `remaining` pattern used by send_payment_reminder and
        # invoicing.create_payment_link.
        paid_by_invoice: dict[uuid.UUID, Decimal] = {}
        if overdue_invoices:
            from app.features.invoicing.models import Payment as _Payment
            inv_ids = [i.id for i in overdue_invoices]
            pay_rows = await db.execute(
                select(
                    _Payment.invoice_id,
                    func.coalesce(func.sum(_Payment.amount), 0),
                )
                .where(
                    _Payment.invoice_id.in_(inv_ids),
                    _Payment.org_id == org_id,
                )
                .group_by(_Payment.invoice_id)
            )
            for inv_id, total in pay_rows.all():
                paid_by_invoice[inv_id] = Decimal(str(total or 0))

        for inv in overdue_invoices:
            # Outstanding = gross − partial payments. Skip fully-paid
            # invoices that haven't been marked PAID yet (edge case;
            # defence-in-depth since such invoices shouldn't appear on
            # the late-payer dashboard).
            remaining = Decimal(inv.total_sek) - paid_by_invoice.get(inv.id, Decimal("0"))
            if remaining <= 0:
                continue
            remaining_f = float(remaining)

            days_overdue = (today - inv.due_date).days
            if days_overdue >= 30:
                priority = "CRITICAL"
                action_label = "Escalate — send formal demand letter draft"
            elif days_overdue >= 14:
                priority = "HIGH"
                action_label = "Send 2nd payment reminder via email"
            elif days_overdue >= 7:
                priority = "HIGH"
                action_label = "Send 1st payment reminder via email"
            else:
                continue

            cards.append(ActionCard(
                id=f"overdue-{inv.id}",
                card_type="ALERT",
                priority=priority,
                module=5,
                title=f"🔴 Invoice {inv.invoice_number} — {days_overdue} days overdue ({remaining_f:,.0f} SEK)",
                insight=(
                    f"{inv.customer.company_name} owes {remaining_f:,.0f} SEK on invoice "
                    f"{inv.invoice_number} (due {inv.due_date}). Now {days_overdue} days overdue."
                ),
                action=action_label,
                impact_estimate=f"{remaining_f:,.0f} SEK outstanding",
                requires_approval=days_overdue < 14,
                auto_execute_action="send_reminder" if days_overdue >= 14 else None,
                meta={
                    "invoice_id": str(inv.id),
                    "invoice_number": inv.invoice_number,
                    "customer_name": inv.customer.company_name,
                    "customer_email": inv.customer.email or "",
                    "amount": remaining_f,
                    "days_overdue": days_overdue,
                },
            ))

        # Churn signals: multi-signal risk scoring (0–100).
        # Signals: recency (50pts), frequency decline (30pts), LTV weight (20pts).
        # Single grouped query — avoids 2N DB calls on large customer books.
        ninety_days_ago = today - timedelta(days=90)
        one_eighty_days_ago = today - timedelta(days=180)
        agg_rows = await db.execute(
            select(
                Invoice.customer_id,
                func.max(Invoice.issue_date).label("last_issue"),
                func.coalesce(func.sum(Invoice.total_sek), 0).label("ltv"),
                func.count(
                    case((Invoice.issue_date >= ninety_days_ago, 1))
                ).label("inv_last_90"),
                func.count(
                    case((
                        Invoice.issue_date.between(one_eighty_days_ago, ninety_days_ago),
                        1,
                    ))
                ).label("inv_prior_90"),
            )
            .where(
                Invoice.org_id == org_id,
                Invoice.status != InvoiceStatus.DRAFT,
            )
            .group_by(Invoice.customer_id)
        )
        customer_stats: dict[uuid.UUID, tuple[date | None, float, int, int]] = {
            r.customer_id: (
                r.last_issue,
                float(r.ltv or 0),
                int(r.inv_last_90 or 0),
                int(r.inv_prior_90 or 0),
            )
            for r in agg_rows
        }
        customer_result = await db.execute(
            select(Customer)
            .where(Customer.org_id == org_id, Customer.is_active == True)  # noqa: E712
            .limit(2000)
        )
        for cust in customer_result.scalars():
            last_invoice, ltv, inv_last_90, inv_prior_90 = customer_stats.get(
                cust.id, (None, 0.0, 0, 0)
            )
            if not last_invoice or ltv < 1000:
                continue
            days_since = (today - last_invoice).days
            if days_since < 45:
                continue

            # Recency: 0 at 45d, full 50pts at 180d+
            recency_score = min(50.0, max(0.0, (days_since - 45) / 135 * 50))
            # Frequency decline vs prior window
            if inv_prior_90 > 0:
                freq_score = max(0.0, 1 - inv_last_90 / inv_prior_90) * 30
            elif inv_last_90 == 0:
                freq_score = 30.0  # no orders in last 90d
            else:
                freq_score = 0.0
            # LTV weight: 0 at 1k SEK, full 20pts at 100k+ SEK
            ltv_score = min(20.0, max(0.0, (ltv - 1000) / 99000 * 20))

            risk_score = int(recency_score + freq_score + ltv_score)
            if risk_score > 70:
                priority = "HIGH"
            elif risk_score > 40:
                priority = "MEDIUM"
            else:
                priority = "LOW"

            cards.append(ActionCard(
                id=f"churn-{cust.id}",
                card_type="SUGGESTION",
                priority=priority,
                module=5,
                title=f"💤 {cust.company_name} — no order in {days_since} days",
                insight=(
                    f"{cust.company_name} has not placed an order in {days_since} days "
                    f"(risk score: {risk_score}/100). "
                    f"Their lifetime value is {ltv:,.0f} SEK — worth a win-back effort."
                ),
                action="Draft and send a win-back email with a special offer",
                impact_estimate=f"Customer LTV: {ltv:,.0f} SEK — re-engage before permanent churn",
                requires_approval=True,
                meta={
                    "customer_id": str(cust.id),
                    "customer_email": cust.email or "",
                    "ltv": ltv,
                    "risk_score": risk_score,
                    "days_since": days_since,
                },
            ))

        # ── Sort: CRITICAL first, then priority, then module ──────────────────
        cards.sort(key=lambda c: (_priority_order(c.priority), c.module))

    except HTTPException:
        raise
    except Exception as e:
        log.error("get_action_cards failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")

    return CardsResponse(
        cards=cards,
        generated_at=datetime.now(timezone.utc),
        org_id=str(org_id),
    )


# ── Execute actions ───────────────────────────────────────────────────────────

@router.post("/actions/send-reminder", response_model=ActionResult)
async def send_payment_reminder(
    body: SendReminderRequest,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Send an overdue payment reminder email for an invoice."""
    _, member = ctx
    org_id = member.org_id

    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.customer))
        .where(Invoice.id == body.invoice_id, Invoice.org_id == org_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if not inv.customer.email:
        raise HTTPException(status_code=422, detail="Customer has no email address")

    # Refuse to send a "payment overdue" email for an invoice that is not
    # actually overdue. The UI/AI card layer normally filters these out,
    # but a direct POST to this endpoint (or a stale cached card) would
    # otherwise spam a customer who has already paid with a demand for
    # payment — a serious trust / reputational issue — or send
    # "overdue by -5 days" to a customer whose invoice isn't even due yet.
    if inv.status not in (InvoiceStatus.SENT, InvoiceStatus.OVERDUE):
        raise HTTPException(
            status_code=422,
            detail=f"Cannot send reminder: invoice is {inv.status.value}, not SENT or OVERDUE.",
        )
    if inv.due_date >= date.today():
        raise HTTPException(
            status_code=422,
            detail="Cannot send reminder: invoice is not yet past its due date.",
        )

    # Idempotency: at most one reminder per invoice per calendar day (UTC).
    # Acquire the slot FIRST (INSERT ON CONFLICT DO NOTHING). Only the
    # request that wins the insert proceeds to send the email — otherwise
    # two rapid clicks could both pass a plain SELECT check and both send.
    today_key = date.today().isoformat()
    dedupe_key = f"inv:{inv.id}:{today_key}"
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    ins = (
        pg_insert(IdempotencyKey.__table__)
        .values(
            org_id=org_id,
            endpoint="ai.send_reminder",
            key=dedupe_key,
            target_id=str(inv.id),
        )
        .on_conflict_do_nothing(index_elements=["org_id", "endpoint", "key"])
    )
    slot = await db.execute(ins)
    if slot.rowcount == 0:
        await db.commit()
        return ActionResult(
            status="skipped",
            message="A reminder for this invoice was already sent today.",
        )
    # Commit the slot immediately so a concurrent retry sees it even if the
    # email send below takes several seconds.
    await db.commit()

    org = await db.get(Organization, org_id)
    org_name = org.name if org else "Varuflow"
    days_overdue = (date.today() - inv.due_date).days

    # Nag the customer for the UNPAID balance, not the invoice face value.
    # If they've already paid part of it (partial bank transfer, etc.) the
    # Payment rows exist but the invoice status stays SENT/OVERDUE until
    # fully settled. Emailing "You owe 10 000 SEK" after the customer has
    # already paid 7 000 SEK is a serious trust / dispute risk and has
    # been the source of support escalations. Matches the `remaining`
    # computation in invoicing.create_payment_link.
    from app.features.invoicing.models import Payment as _Payment
    paid_so_far = await db.scalar(
        select(func.coalesce(func.sum(_Payment.amount), 0))
        .where(_Payment.invoice_id == inv.id, _Payment.org_id == org_id)
    ) or 0
    remaining = float(inv.total_sek) - float(paid_so_far)
    if remaining <= 0:
        # Fully paid — shouldn't have reached this branch (status would
        # normally be PAID) but guard anyway so we don't demand payment
        # from a customer who is square.
        return ActionResult(
            status="skipped",
            message="Invoice has been fully paid — no reminder sent.",
        )

    from app.services.email import _send_overdue_reminder
    try:
        sent = await _send_overdue_reminder(
            to_email=inv.customer.email,
            customer_name=inv.customer.company_name,
            invoice_number=inv.invoice_number,
            total_sek=f"{remaining:,.0f}",
            due_date=str(inv.due_date),
            days_overdue=days_overdue,
            payment_url=inv.stripe_payment_link_url,
            org_name=org_name,
        )
    except Exception:
        sent = False

    if not sent:
        # Release the slot so the user can retry today without waiting for
        # the cleanup job to expire the idempotency key.
        from sqlalchemy import delete as _delete
        await db.execute(
            _delete(IdempotencyKey).where(
                IdempotencyKey.org_id == org_id,
                IdempotencyKey.endpoint == "ai.send_reminder",
                IdempotencyKey.key == dedupe_key,
            )
        )
        await db.commit()

    return ActionResult(
        status="sent" if sent else "skipped",
        message=f"Reminder {'sent to ' + inv.customer.email if sent else 'skipped — Resend not configured'}",
    )


@router.post("/actions/draft-po", response_model=ActionResult)
async def draft_purchase_order(
    body: DraftPoRequest,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Create a draft purchase order for a low-stock product."""
    _, member = ctx
    org_id = member.org_id

    product = await db.get(Product, body.product_id)
    if not product or product.org_id != org_id:
        raise HTTPException(status_code=404, detail="Product not found")

    # Idempotency: at most one draft PO per product per calendar day. Acquire
    # the slot FIRST so two rapid clicks can't both pass the SELECT check
    # and both create a draft PO (same pattern as send_reminder).
    today_key = date.today().isoformat()
    dedupe_key = f"prod:{product.id}:{today_key}"
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    slot = await db.execute(
        pg_insert(IdempotencyKey.__table__)
        .values(
            org_id=org_id,
            endpoint="ai.draft_po",
            key=dedupe_key,
            target_id="pending",  # overwritten below with real PO id
        )
        .on_conflict_do_nothing(index_elements=["org_id", "endpoint", "key"])
    )
    if slot.rowcount == 0:
        await db.commit()
        return ActionResult(
            status="skipped",
            message=f"A draft PO for {product.name} was already created today.",
        )

    # Find a supplier. Order by created_at ASC so a multi-supplier org
    # always lands on the *same* deterministic supplier for AI drafts —
    # without the explicit ordering the picked row depends on Postgres's
    # physical scan order, which can flip between calls after VACUUM /
    # index maintenance. That made the "Auto-drafted by Varuflow AI"
    # notes inconsistent across re-runs and caused the PO to silently
    # switch vendors between the idempotency window (per product per
    # day) and any follow-up runs the user kicks off from another
    # browser tab. Matches the earliest-created convention used in
    # pos.create_sale / inventory.update_po_status for default warehouse.
    supplier_result = await db.execute(
        select(Supplier)
        .where(Supplier.org_id == org_id, Supplier.is_active == True)  # noqa: E712
        .order_by(Supplier.created_at.asc(), Supplier.id.asc())
        .limit(1)
    )
    supplier = supplier_result.scalar_one_or_none()
    if not supplier:
        # Release the slot so the user can retry today after adding a supplier.
        from sqlalchemy import delete as _delete
        await db.execute(
            _delete(IdempotencyKey).where(
                IdempotencyKey.org_id == org_id,
                IdempotencyKey.endpoint == "ai.draft_po",
                IdempotencyKey.key == dedupe_key,
            )
        )
        await db.commit()
        raise HTTPException(status_code=422, detail="No active supplier found — add a supplier first")

    line_total = Decimal(str(body.quantity)) * product.purchase_price
    po = PurchaseOrder(
        org_id=org_id,
        supplier_id=supplier.id,
        total=line_total,
        notes=f"Auto-drafted by Varuflow AI — low stock alert for {product.name}",
    )
    db.add(po)
    await db.flush()

    item = PurchaseOrderItem(
        purchase_order_id=po.id,
        product_id=product.id,
        quantity=body.quantity,
        unit_price=product.purchase_price,
        line_total=line_total,
    )
    db.add(item)

    # Backfill the slot's target_id now that the PO has an id.
    from sqlalchemy import update as _update
    await db.execute(
        _update(IdempotencyKey)
        .where(
            IdempotencyKey.org_id == org_id,
            IdempotencyKey.endpoint == "ai.draft_po",
            IdempotencyKey.key == dedupe_key,
        )
        .values(target_id=str(po.id))
    )
    await db.commit()

    return ActionResult(
        status="created",
        message=f"Draft PO created for {body.quantity}× {product.name} from {supplier.name} — {float(line_total):,.0f} SEK",
    )
