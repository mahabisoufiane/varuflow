"""Live business context builder for the AI chat endpoint.

Pulled out of ``routers/integrations.py`` so the context assembly is
unit-testable in isolation. Returns both a structured ``AiContext``
(used to render frontend chips) and a plain-text summary (injected
into the GPT-4o system prompt).

Scope: inventory + invoicing. Does not touch PII beyond the customer
display name already shown on the dashboard.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class LowStockItem:
    name: str
    sku: str | None
    quantity: int
    reorder_level: int


@dataclass
class OverdueInvoice:
    invoice_number: str
    customer_name: str
    remaining_sek: float
    days_overdue: int


@dataclass
class AiContext:
    today: date
    low_stock: list[LowStockItem] = field(default_factory=list)
    revenue_30d_sek: float = 0.0
    overdue: list[OverdueInvoice] = field(default_factory=list)
    current_month_sek: float = 0.0
    prev_month_sek: float = 0.0

    @property
    def month_delta_pct(self) -> float | None:
        """Current-vs-previous-month sales delta. ``None`` when the
        previous month had no revenue (division would be meaningless).
        """
        if self.prev_month_sek <= 0:
            return None
        return (self.current_month_sek - self.prev_month_sek) / self.prev_month_sek * 100.0

    def to_prompt_string(self) -> str:
        """Render a compact, deterministic block for the system prompt.

        Ordering is stable so a given business state always produces
        the same prompt — easier to cache, diff, and test against.
        """
        lines: list[str] = []
        if self.low_stock:
            ls = ", ".join(
                f"{it.name} ({it.quantity} kvar, beställningsnivå {it.reorder_level})"
                for it in self.low_stock
            )
            lines.append(f"Top low-stock products: {ls}.")
        else:
            lines.append("No products are currently below reorder level.")

        lines.append(f"Revenue last 30 days: {self.revenue_30d_sek:,.0f} SEK.")

        if self.overdue:
            ov = "; ".join(
                f"{it.customer_name} — {it.remaining_sek:,.0f} SEK, {it.days_overdue} d overdue"
                for it in self.overdue
            )
            lines.append(f"Most overdue invoices: {ov}.")
        else:
            lines.append("No overdue invoices.")

        delta = self.month_delta_pct
        if delta is None:
            lines.append("Sales month-over-month: previous month had no revenue.")
        else:
            sign = "+" if delta >= 0 else ""
            lines.append(
                f"Sales this month vs last month: {sign}{delta:.1f}% "
                f"({self.current_month_sek:,.0f} SEK vs {self.prev_month_sek:,.0f} SEK)."
            )
        return " ".join(lines)


def _first_of_month(d: date) -> date:
    return d.replace(day=1)


def _first_of_prev_month(d: date) -> date:
    if d.month == 1:
        return date(d.year - 1, 12, 1)
    return date(d.year, d.month - 1, 1)


async def build_ai_context(
    db: AsyncSession,
    *,
    org_id: UUID,
    today: date | None = None,
) -> AiContext:
    """Assemble the live business snapshot for the AI chat endpoint."""
    # Local imports — keep this module importable by the migration runner
    # even before all ORM models have loaded.
    from app.features.inventory.models import Product, StockLevel
    from app.features.invoicing.models import Customer, Invoice, InvoiceStatus, Payment

    today = today or date.today()
    thirty_days_ago = today - timedelta(days=30)
    current_month_start = _first_of_month(today)
    prev_month_start = _first_of_prev_month(today)

    ctx = AiContext(today=today)

    # ── Top 5 low-stock products ──────────────────────────────────────────
    # Aggregate quantity across all warehouses per product. Matches the
    # canonical signal used by the scheduler's low_stock job and the AI
    # action cards (Product.reorder_level, not StockLevel.min_threshold).
    low_rows = (
        await db.execute(
            select(
                Product.name,
                Product.sku,
                Product.reorder_level,
                func.coalesce(func.sum(StockLevel.quantity), 0).label("quantity"),
            )
            .outerjoin(StockLevel, StockLevel.product_id == Product.id)
            .where(
                Product.org_id == org_id,
                Product.is_active == True,  # noqa: E712
                Product.reorder_level > 0,
            )
            .group_by(Product.id, Product.name, Product.sku, Product.reorder_level)
            .having(
                func.coalesce(func.sum(StockLevel.quantity), 0) <= Product.reorder_level,
            )
            # Order by closeness to zero so the 5 most critical items come first.
            .order_by(func.coalesce(func.sum(StockLevel.quantity), 0).asc())
            .limit(5)
        )
    ).all()
    ctx.low_stock = [
        LowStockItem(
            name=r.name,
            sku=r.sku,
            quantity=int(r.quantity),
            reorder_level=int(r.reorder_level),
        )
        for r in low_rows
    ]

    # ── Revenue last 30 days (PAID invoices) ──────────────────────────────
    rev_30d = await db.scalar(
        select(func.coalesce(func.sum(Invoice.total_sek), 0))
        .where(
            Invoice.org_id == org_id,
            Invoice.status == InvoiceStatus.PAID,
            Invoice.issue_date >= thirty_days_ago,
        )
    )
    ctx.revenue_30d_sek = float(rev_30d or 0)

    # ── 3 most overdue invoices ───────────────────────────────────────────
    paid_subq = (
        select(
            Payment.invoice_id.label("invoice_id"),
            func.coalesce(func.sum(Payment.amount), 0).label("paid"),
        )
        .where(Payment.org_id == org_id)
        .group_by(Payment.invoice_id)
        .subquery()
    )
    remaining_expr = Invoice.total_sek - func.coalesce(paid_subq.c.paid, 0)
    overdue_rows = (
        await db.execute(
            select(
                Invoice.invoice_number,
                Customer.company_name,
                remaining_expr.label("remaining"),
                Invoice.due_date,
            )
            .join(Customer, Customer.id == Invoice.customer_id)
            .outerjoin(paid_subq, paid_subq.c.invoice_id == Invoice.id)
            .where(
                Invoice.org_id == org_id,
                Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE]),
                Invoice.due_date < today,
                remaining_expr > 0,
            )
            # Most overdue first (oldest due_date).
            .order_by(Invoice.due_date.asc())
            .limit(3)
        )
    ).all()
    ctx.overdue = [
        OverdueInvoice(
            invoice_number=r.invoice_number,
            customer_name=r.company_name,
            remaining_sek=float(r.remaining),
            days_overdue=(today - r.due_date).days,
        )
        for r in overdue_rows
    ]

    # ── Month-over-month sales ───────────────────────────────────────────
    # Revenue recognised on issue_date (matches the dashboard KPI).
    curr_sales = await db.scalar(
        select(func.coalesce(func.sum(Invoice.total_sek), 0))
        .where(
            Invoice.org_id == org_id,
            Invoice.status == InvoiceStatus.PAID,
            Invoice.issue_date >= current_month_start,
            Invoice.issue_date <= today,
        )
    )
    prev_sales = await db.scalar(
        select(func.coalesce(func.sum(Invoice.total_sek), 0))
        .where(
            Invoice.org_id == org_id,
            Invoice.status == InvoiceStatus.PAID,
            Invoice.issue_date >= prev_month_start,
            Invoice.issue_date < current_month_start,
        )
    )
    ctx.current_month_sek = float(curr_sales or 0)
    ctx.prev_month_sek = float(prev_sales or 0)

    return ctx
