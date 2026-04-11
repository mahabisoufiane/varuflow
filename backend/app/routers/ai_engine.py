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
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_plan
from app.models.inventory import (
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    StockLevel,
    StockMovement,
    StockMovementType,
    Supplier,
)
from app.models.invoicing import Customer, Invoice, InvoiceStatus, Payment
from app.models.organization import OrgPlan, Organization

router = APIRouter(
    prefix="/api/ai",
    tags=["ai"],
    dependencies=[Depends(require_plan(OrgPlan.PRO))],
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
    quantity: int


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

    # ── MODULE 1: Inventory Intelligence ──────────────────────────────────────

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

    # Stock levels with products
    stock_rows = await db.execute(
        select(StockLevel, Product)
        .join(Product, StockLevel.product_id == Product.id)
        .where(Product.org_id == org_id, Product.is_active == True)  # noqa: E712
    )
    for sl, p in stock_rows:
        avg_daily = velocity_map.get(p.id, 0.0)

        # Stockout risk
        if avg_daily > 0:
            days_left = sl.quantity / avg_daily
            if days_left <= DEFAULT_LEAD_DAYS:
                priority: Priority = "CRITICAL" if days_left <= 1 else "HIGH"
                cards.append(ActionCard(
                    id=f"stockout-{p.id}",
                    card_type="ALERT",
                    priority=priority,
                    module=1,
                    title=f"⚠️ {p.name} will run out in ~{days_left:.1f} days",
                    insight=(
                        f"{p.name} ({p.sku}) has {sl.quantity} units left with an average "
                        f"of {avg_daily:.1f} units sold per day. At current velocity, stock "
                        f"runs out in ~{days_left:.1f} days — within supplier lead time."
                    ),
                    action=f"Draft purchase order for {p.name} — recommend ordering {max(10, int(avg_daily * 14))} units",
                    impact_estimate=f"Stockout loss estimated {int(avg_daily * 3 * float(p.sell_price)):,} SEK over 3 days",
                    requires_approval=True,
                    auto_execute_action="draft_po",
                    meta={"product_id": str(p.id), "product_name": p.name, "suggested_qty": max(10, int(avg_daily * 14))},
                ))
        elif sl.quantity <= sl.min_threshold and sl.min_threshold > 0:
            cards.append(ActionCard(
                id=f"minthreshold-{p.id}",
                card_type="ALERT",
                priority="HIGH",
                module=1,
                title=f"📦 {p.name} below reorder point",
                insight=(
                    f"{p.name} ({p.sku}) has {sl.quantity} units — at or below the reorder "
                    f"threshold of {sl.min_threshold}. No recent sales velocity data."
                ),
                action=f"Review and restock {p.name}",
                impact_estimate="Risk of stockout if demand resumes",
                requires_approval=True,
                auto_execute_action="draft_po",
                meta={"product_id": str(p.id), "product_name": p.name, "suggested_qty": sl.min_threshold * 3},
            ))

        # Dead stock: no OUT movements in 30+ days
        thirty_days_ago = today - timedelta(days=30)
        has_recent_sale = await db.scalar(
            select(func.count()).where(
                StockMovement.product_id == p.id,
                StockMovement.type == StockMovementType.OUT,
                StockMovement.created_at >= thirty_days_ago,
            )
        ) or 0

        if has_recent_sale == 0 and sl.quantity > 0:
            stock_value = sl.quantity * float(p.purchase_price)
            cards.append(ActionCard(
                id=f"deadstock-{p.id}",
                card_type="SUGGESTION",
                priority="MEDIUM",
                module=1,
                title=f"🛑 Dead stock: {p.name} — {sl.quantity} units unsold for 30+ days",
                insight=(
                    f"{p.name} has {sl.quantity} units with no sales in over 30 days. "
                    f"Tied-up capital: ~{stock_value:,.0f} SEK. Consider a clearance action."
                ),
                action=f"Run clearance promotion at 15% discount or bundle with a fast-moving product",
                impact_estimate=f"Recover up to {stock_value:,.0f} SEK in tied-up inventory capital",
                requires_approval=True,
                meta={"product_id": str(p.id), "product_name": p.name},
            ))

    # ── MODULE 2: Margin & Pricing Optimizer ──────────────────────────────────

    products_result = await db.execute(
        select(Product).where(Product.org_id == org_id, Product.is_active == True)  # noqa: E712
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

    # ── MODULE 5: Customer Intelligence ───────────────────────────────────────

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
    )
    for inv in overdue_result.scalars():
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
            title=f"🔴 Invoice {inv.invoice_number} — {days_overdue} days overdue ({float(inv.total_sek):,.0f} SEK)",
            insight=(
                f"{inv.customer.company_name} owes {float(inv.total_sek):,.0f} SEK on invoice "
                f"{inv.invoice_number} (due {inv.due_date}). Now {days_overdue} days overdue."
            ),
            action=action_label,
            impact_estimate=f"{float(inv.total_sek):,.0f} SEK outstanding",
            requires_approval=days_overdue < 14,
            auto_execute_action="send_reminder" if days_overdue >= 14 else None,
            meta={
                "invoice_id": str(inv.id),
                "invoice_number": inv.invoice_number,
                "customer_name": inv.customer.company_name,
                "customer_email": inv.customer.email or "",
                "amount": float(inv.total_sek),
                "days_overdue": days_overdue,
            },
        ))

    # Churn signals: customers with no invoices in 45+ days
    forty_five_days_ago = today - timedelta(days=45)
    customer_result = await db.execute(
        select(Customer).where(Customer.org_id == org_id, Customer.is_active == True)  # noqa: E712
    )
    for cust in customer_result.scalars():
        last_invoice = await db.scalar(
            select(func.max(Invoice.issue_date)).where(
                Invoice.customer_id == cust.id,
                Invoice.status != InvoiceStatus.DRAFT,
            )
        )
        if last_invoice and last_invoice < forty_five_days_ago:
            days_since = (today - last_invoice).days
            # Calculate LTV
            ltv = await db.scalar(
                select(func.coalesce(func.sum(Invoice.total_sek), 0)).where(
                    Invoice.customer_id == cust.id,
                    Invoice.status != InvoiceStatus.DRAFT,
                )
            ) or 0
            if float(ltv) > 5000:  # Only flag valuable customers
                cards.append(ActionCard(
                    id=f"churn-{cust.id}",
                    card_type="SUGGESTION",
                    priority="MEDIUM",
                    module=5,
                    title=f"💤 {cust.company_name} — no order in {days_since} days",
                    insight=(
                        f"{cust.company_name} has not placed an order in {days_since} days. "
                        f"Their lifetime value is {float(ltv):,.0f} SEK — worth a win-back effort."
                    ),
                    action="Draft and send a win-back email with a special offer",
                    impact_estimate=f"Customer LTV: {float(ltv):,.0f} SEK — re-engage before permanent churn",
                    requires_approval=True,
                    meta={"customer_id": str(cust.id), "customer_email": cust.email or "", "ltv": float(ltv)},
                ))

    # ── Sort: CRITICAL first, then priority, then module ──────────────────────
    cards.sort(key=lambda c: (_priority_order(c.priority), c.module))

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

    org = await db.get(Organization, org_id)
    org_name = org.name if org else "Varuflow"
    days_overdue = (date.today() - inv.due_date).days

    from app.services.email import _send_overdue_reminder
    sent = await _send_overdue_reminder(
        to_email=inv.customer.email,
        customer_name=inv.customer.company_name,
        invoice_number=inv.invoice_number,
        total_sek=f"{float(inv.total_sek):,.0f}",
        due_date=str(inv.due_date),
        days_overdue=days_overdue,
        payment_url=inv.stripe_payment_link_url,
        org_name=org_name,
    )

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

    # Find a supplier (use first available for this org)
    supplier_result = await db.execute(
        select(Supplier).where(Supplier.org_id == org_id, Supplier.is_active == True).limit(1)  # noqa: E712
    )
    supplier = supplier_result.scalar_one_or_none()
    if not supplier:
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
    await db.commit()

    return ActionResult(
        status="created",
        message=f"Draft PO created for {body.quantity}× {product.name} from {supplier.name} — {float(line_total):,.0f} SEK",
    )
