"""Analytics: revenue over time, top customers, top products, inventory value, overdue summary."""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_plan
from app.models.inventory import Product, PurchaseOrder, PurchaseOrderStatus, StockLevel, StockMovement, Warehouse
from app.models.invoicing import Customer, Invoice, InvoiceLineItem, InvoiceStatus, Payment
from app.models.organization import OrgPlan
router = APIRouter(prefix="/api/analytics", tags=["analytics"])

NAVY = colors.HexColor("#1a2332")
LIGHT_GRAY = colors.HexColor("#f3f4f6")


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Schemas ────────────────────────────────────────────────────────────────────

class RevenuePoint(BaseModel):
    month: str          # "2025-01"
    invoiced: Decimal
    collected: Decimal


class TopCustomer(BaseModel):
    customer_id: uuid.UUID
    company_name: str
    total_invoiced: Decimal
    invoice_count: int


class TopProduct(BaseModel):
    product_id: uuid.UUID | None
    description: str
    revenue: Decimal
    quantity_sold: Decimal


class StatusBucket(BaseModel):
    status: str
    count: int
    total: Decimal


class InventorySummary(BaseModel):
    total_products: int
    total_stock_value: Decimal
    low_stock_count: int
    warehouse_count: int
    # Item 41 — count of products projected to stock out within the
    # next 30 days by the forecasting engine. Optional so callers on
    # pre-Item-41 clients don't break parsing the payload.
    stockout_risk_count: int = 0


class OverdueSummary(BaseModel):
    overdue_count: int
    overdue_total: Decimal
    oldest_days: int


class ExpenseSummary(BaseModel):
    # Item 43 — quick totals surfaced on the overview dashboard.
    # ``pending_approval`` gives owners the queue depth at a glance
    # so they can triage without opening the expenses page.
    total_amount: Decimal = Decimal("0")
    count: int = 0
    pending_approval: int = 0


class AnalyticsOverview(BaseModel):
    from_date: date
    to_date: date
    revenue_points: list[RevenuePoint]
    top_customers: list[TopCustomer]
    top_products: list[TopProduct]
    status_breakdown: list[StatusBucket]
    inventory: InventorySummary
    overdue: OverdueSummary
    expenses: ExpenseSummary = Field(default_factory=ExpenseSummary)


# ── Helpers ───────────────────────────────────────────────────────────────────

# Analytics queries iterate one DB round-trip per month in the range. A
# malicious or buggy client asking for 100+ years would pin the DB; cap the
# range to a sane maximum (24 months covers the longest real use-case: YoY).
_MAX_ANALYTICS_MONTHS = 24


def _clamp_analytics_range(from_date: date | None, to_date: date | None) -> tuple[date, date]:
    today = date.today()
    if to_date is None:
        to_date = today
    if from_date is None:
        from_date = (today.replace(day=1) - timedelta(days=11 * 28)).replace(day=1)
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must be before to_date")
    # Cap the window at _MAX_ANALYTICS_MONTHS by pushing from_date forward.
    months_span = (to_date.year - from_date.year) * 12 + (to_date.month - from_date.month)
    if months_span > _MAX_ANALYTICS_MONTHS:
        # Walk from_date forward to exactly _MAX_ANALYTICS_MONTHS before to_date.
        year = to_date.year
        month = to_date.month - _MAX_ANALYTICS_MONTHS
        while month <= 0:
            month += 12
            year -= 1
        from_date = date(year, month, 1)
    return from_date, to_date


async def _stockout_risk_count(db, org_id: uuid.UUID) -> int:
    """Count products projected to stock out within 30 days (Item 41).

    Reuses the forecasting engine so "low stock" (threshold-based) and
    "stockout risk" (velocity-based) stay in lock-step — owners see
    both numbers on the overview dashboard without re-implementing
    the forecast math here. Failures are swallowed so a broken
    forecast doesn't 500 the whole analytics overview.
    """
    try:
        from app.services import forecasting_engine as _fc

        rows = await _fc.gather_product_metrics(db, org_id=org_id)
        return sum(1 for r in rows if r.at_risk)
    except Exception:  # noqa: BLE001 — degrade gracefully
        return 0


async def _expense_summary(
    db, org_id: uuid.UUID, from_date: date, to_date: date,
) -> "ExpenseSummary":
    """Aggregate expense totals for the overview dashboard (Item 43).

    Only APPROVED expenses count towards the total so the dashboard
    mirrors the owner's books; DRAFT rows are reported separately as
    a queue-depth number. Degrades gracefully — a missing
    ``expenses`` table (pre-v57 environment) returns zeros rather
    than 500ing the entire overview.
    """
    try:
        from sqlalchemy import func as _f, select as _select

        from app.models.expenses import Expense as _E, ExpenseStatus as _ES

        approved_row = (
            await db.execute(
                _select(
                    _f.coalesce(_f.sum(_E.amount), 0),
                    _f.count(_E.id),
                ).where(
                    _E.org_id == org_id,
                    _E.status == _ES.APPROVED,
                    _E.expense_date >= from_date,
                    _E.expense_date <= to_date,
                )
            )
        ).one()
        pending = (
            await db.scalar(
                _select(_f.count(_E.id)).where(
                    _E.org_id == org_id, _E.status == _ES.DRAFT,
                )
            )
        ) or 0
        return ExpenseSummary(
            total_amount=Decimal(str(approved_row[0] or 0)),
            count=int(approved_row[1] or 0),
            pending_approval=int(pending),
        )
    except Exception:  # noqa: BLE001
        return ExpenseSummary()


def _month_range(from_date: date, to_date: date) -> list[tuple[date, date]]:
    """Return list of (first, last) pairs for each month in [from_date, to_date]."""
    months = []
    current = from_date.replace(day=1)
    end = to_date.replace(day=1)
    while current <= end:
        if current.month == 12:
            nxt = current.replace(year=current.year + 1, month=1)
        else:
            nxt = current.replace(month=current.month + 1)
        last = nxt - timedelta(days=1)
        months.append((current, min(last, to_date)))
        current = nxt
    return months


# ── Overview endpoint ──────────────────────────────────────────────────────────

@router.get("/overview", response_model=AnalyticsOverview)
async def get_overview(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    from_date: date = Query(default=None),
    to_date: date = Query(default=None),
    segment_id: uuid.UUID | None = Query(default=None),
):
    org_id = _org(ctx)
    today = date.today()

    from_date, to_date = _clamp_analytics_range(from_date, to_date)

    # Item 39 — optional segment filter. When supplied, every query
    # below that joins on ``Invoice.customer_id`` is further narrowed
    # to customers inside the segment. We resolve the list of customer
    # ids once up-front via the segmentation service (which enforces
    # org-ownership) rather than threading a subquery into every agg.
    segment_customer_ids: list[uuid.UUID] | None = None
    if segment_id is not None:
        from app.services import segmentation_engine as _seg_svc

        segment_customer_ids = await _seg_svc.list_segment_customer_ids(
            db, segment_id=segment_id, org_id=org_id,
        )
        # Empty segment → every aggregate is guaranteed-empty. Short-
        # circuiting with an impossible id keeps the query planner
        # happy without special-casing the ``.where(...in_(...))`` API.
        if not segment_customer_ids:
            segment_customer_ids = [uuid.UUID("00000000-0000-0000-0000-000000000000")]

    # ── Revenue by month ───────────────────────────────────────────────────
    # Two aggregated queries (one per data source) instead of 2N round-trips
    # where N is the number of months in the range. A 24-month range went
    # from 48 DB calls to 2.
    month_buckets = _month_range(from_date, to_date)
    invoiced_by_month = dict(
        (
            await db.execute(
                (
                    select(
                        func.to_char(Invoice.issue_date, "YYYY-MM").label("m"),
                        func.coalesce(func.sum(Invoice.total_sek * Invoice.exchange_rate), 0).label("total"),
                    )
                    .where(
                        Invoice.org_id == org_id,
                        Invoice.issue_date >= from_date,
                        Invoice.issue_date <= to_date,
                        Invoice.status != InvoiceStatus.DRAFT,
                        *(
                            [Invoice.customer_id.in_(segment_customer_ids)]
                            if segment_customer_ids is not None
                            else []
                        ),
                    )
                    .group_by("m")
                )
            )
        ).all()
    )
    collected_by_month = dict(
        (
            await db.execute(
                select(
                    func.to_char(Payment.payment_date, "YYYY-MM").label("m"),
                    func.coalesce(func.sum(Payment.amount * Payment.exchange_rate), 0).label("total"),
                )
                .where(
                    Payment.org_id == org_id,
                    Payment.payment_date >= from_date,
                    Payment.payment_date <= to_date,
                )
                .group_by("m")
            )
        ).all()
    )
    revenue_points: list[RevenuePoint] = []
    for first, _last in month_buckets:
        key = first.strftime("%Y-%m")
        revenue_points.append(RevenuePoint(
            month=key,
            invoiced=Decimal(str(invoiced_by_month.get(key, 0))),
            collected=Decimal(str(collected_by_month.get(key, 0))),
        ))

    # ── Top customers ──────────────────────────────────────────────────────
    top_customers_stmt = (
        select(
            Invoice.customer_id,
            Customer.company_name,
            func.sum(Invoice.total_sek * Invoice.exchange_rate).label("total_invoiced"),
            func.count(Invoice.id).label("invoice_count"),
        )
        .join(Customer, Invoice.customer_id == Customer.id)
        .where(
            Invoice.org_id == org_id,
            Invoice.issue_date >= from_date,
            Invoice.issue_date <= to_date,
            Invoice.status != InvoiceStatus.DRAFT,
        )
        .group_by(Invoice.customer_id, Customer.company_name)
        .order_by(func.sum(Invoice.total_sek * Invoice.exchange_rate).desc())
        .limit(5)
    )
    if segment_customer_ids is not None:
        top_customers_stmt = top_customers_stmt.where(
            Invoice.customer_id.in_(segment_customer_ids),
        )
    top_rows = await db.execute(top_customers_stmt)
    top_customers = [
        TopCustomer(
            customer_id=row.customer_id,
            company_name=row.company_name,
            total_invoiced=Decimal(str(row.total_invoiced)),
            invoice_count=row.invoice_count,
        )
        for row in top_rows
    ]

    # ── Top products by revenue ────────────────────────────────────────────
    product_rows = await db.execute(
        select(
            InvoiceLineItem.product_id,
            InvoiceLineItem.description,
            func.sum(InvoiceLineItem.line_total).label("revenue"),
            func.sum(InvoiceLineItem.quantity).label("quantity_sold"),
        )
        .join(Invoice, InvoiceLineItem.invoice_id == Invoice.id)
        .where(
            Invoice.org_id == org_id,
            Invoice.issue_date >= from_date,
            Invoice.issue_date <= to_date,
            Invoice.status != InvoiceStatus.DRAFT,
        )
        .group_by(InvoiceLineItem.product_id, InvoiceLineItem.description)
        .order_by(func.sum(InvoiceLineItem.line_total).desc())
        .limit(10)
    )
    top_products = [
        TopProduct(
            product_id=row.product_id,
            description=row.description,
            revenue=Decimal(str(row.revenue)),
            quantity_sold=Decimal(str(row.quantity_sold)),
        )
        for row in product_rows
    ]

    # ── Invoice status breakdown ───────────────────────────────────────────
    status_rows = await db.execute(
        select(
            Invoice.status,
            func.count(Invoice.id).label("cnt"),
            func.coalesce(func.sum(Invoice.total_sek * Invoice.exchange_rate), 0).label("total"),
        )
        .where(
            Invoice.org_id == org_id,
            Invoice.issue_date >= from_date,
            Invoice.issue_date <= to_date,
        )
        .group_by(Invoice.status)
    )
    status_breakdown = [
        StatusBucket(status=row.status, count=row.cnt, total=Decimal(str(row.total)))
        for row in status_rows
    ]

    # ── Inventory ──────────────────────────────────────────────────────────
    product_count = await db.scalar(
        select(func.count()).where(Product.org_id == org_id, Product.is_active == True)  # noqa: E712
    ) or 0
    warehouse_count = await db.scalar(
        select(func.count()).where(Warehouse.org_id == org_id, Warehouse.is_active == True)  # noqa: E712
    ) or 0
    # Aggregate in the database instead of streaming every StockLevel row
    # into Python memory. A tenant with 100k products across 10 warehouses
    # (1M stock rows) would otherwise OOM the worker on every /overview
    # call. `purchase_price` and `quantity` are both NUMERIC — the product
    # stays exact.
    stock_value_row = await db.execute(
        select(
            func.coalesce(func.sum(StockLevel.quantity * Product.purchase_price), 0)
        )
        .select_from(StockLevel)
        .join(Product, StockLevel.product_id == Product.id)
        .where(Product.org_id == org_id, Product.is_active == True)  # noqa: E712
    )
    stock_value = Decimal(str(stock_value_row.scalar() or 0))
    # Count products whose total on-hand (summed across every warehouse)
    # is at or below their `reorder_level` — the canonical reorder
    # trigger written by Product create/update and the CSV importer,
    # and the same field `_check_low_stock` / `_send_weekly_digest`
    # scheduler jobs use for their alerts.
    #
    # The previous query compared against `StockLevel.min_threshold`,
    # which no endpoint ever writes to (default=0 forever), so after
    # the `min_threshold > 0` guard the low-stock KPI was permanently
    # 0 on the dashboard — contradicting the weekly-digest email that
    # correctly flagged the same products as low. Use `reorder_level`
    # here so the dashboard, digest email and AI action cards all
    # agree on what "low stock" means.
    low_stock_subq = (
        select(Product.id)
        .outerjoin(StockLevel, StockLevel.product_id == Product.id)
        .where(
            Product.org_id == org_id,
            Product.is_active == True,  # noqa: E712
            Product.reorder_level > 0,
        )
        .group_by(Product.id, Product.reorder_level)
        .having(
            func.coalesce(func.sum(StockLevel.quantity), 0) <= Product.reorder_level
        )
        .subquery()
    )
    low_stock = await db.scalar(
        select(func.count()).select_from(low_stock_subq)
    ) or 0

    # ── Overdue ────────────────────────────────────────────────────────────
    # Aggregate overdue count/sum/oldest in the database; the previous
    # implementation materialised every Invoice row, OOMing on tenants
    # with large AR backlogs.
    #
    # Subtract partial payments so the dashboard KPI shows the REMAINING
    # unpaid balance, not the invoice face value. An invoice with a
    # 10 000 SEK total and a 7 000 SEK bank-transfer partial would
    # previously inflate "overdue total" by the collected-but-not-
    # settled 7 000 SEK, and the invoice count included fully-paid rows
    # that just hadn't been flipped to PAID yet. Matches the fix applied
    # to ai_engine late-payer cards and the aging_report endpoint.
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
    overdue_row = (
        await db.execute(
            select(
                func.count(Invoice.id),
                func.coalesce(func.sum(remaining_expr), 0),
                func.min(Invoice.due_date),
            )
            .select_from(Invoice)
            .outerjoin(paid_subq, paid_subq.c.invoice_id == Invoice.id)
            .where(
                Invoice.org_id == org_id,
                Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE]),
                Invoice.due_date < today,
                remaining_expr > 0,
            )
        )
    ).one()
    overdue_count_val, overdue_total, oldest_due = overdue_row
    oldest_days = (today - oldest_due).days if oldest_due else 0

    return AnalyticsOverview(
        from_date=from_date,
        to_date=to_date,
        revenue_points=revenue_points,
        top_customers=top_customers,
        top_products=top_products,
        status_breakdown=status_breakdown,
        inventory=InventorySummary(
            total_products=product_count,
            total_stock_value=stock_value,
            low_stock_count=low_stock,
            warehouse_count=warehouse_count,
            stockout_risk_count=await _stockout_risk_count(db, org_id),
        ),
        overdue=OverdueSummary(
            overdue_count=overdue_count_val or 0,
            overdue_total=Decimal(str(overdue_total)),
            oldest_days=oldest_days,
        ),
        expenses=await _expense_summary(db, org_id, from_date, to_date),
    )


# ── Margin analytics (v20 scope) ──────────────────────────────────────────────

class MarginProduct(BaseModel):
    product_id: str
    product_name: str
    sku: str
    category: str | None = None
    revenue: Decimal
    cogs: Decimal
    gross_profit: Decimal
    margin_pct: float
    quantity_sold: Decimal


class MarginOverall(BaseModel):
    revenue: Decimal
    cogs: Decimal
    gross_profit: Decimal
    margin_pct: float
    line_item_count: int


class MarginByCategory(BaseModel):
    category: str
    revenue: Decimal
    cogs: Decimal
    gross_profit: Decimal
    margin_pct: float


class MarginReport(BaseModel):
    from_date: date
    to_date: date
    overall: MarginOverall
    top_products: list[MarginProduct]
    worst_products: list[MarginProduct]
    by_category: list[MarginByCategory]


@router.get("/margins", response_model=MarginReport)
async def get_margins(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    from_date: date = Query(default=None),
    to_date: date = Query(default=None),
    limit: int = Query(10, ge=1, le=50),
    _plan: None = Depends(require_plan(OrgPlan.PRO)),
):
    """Gross-margin analytics for sent/paid invoices in a date range.

    ``revenue`` is ``sum(line_total)`` (excluding VAT).
    ``cogs`` is ``sum(quantity * product.purchase_price)`` — lines with
    no linked product (``product_id IS NULL``) contribute revenue but
    zero COGS, which is the correct accounting treatment for custom
    service lines that have no stock-tied cost basis.
    """
    org_id = _org(ctx)
    from_date, to_date = _clamp_analytics_range(from_date, to_date)

    # Base filter: SENT or PAID invoices issued in window. DRAFT invoices
    # are excluded because they don't represent realised revenue yet.
    invoice_filter = (
        Invoice.org_id == org_id,
        Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.PAID, InvoiceStatus.OVERDUE]),
        Invoice.issue_date >= from_date,
        Invoice.issue_date <= to_date,
    )

    # ── Per-product aggregate ────────────────────────────────────────────────
    # LEFT JOIN so lines with deleted product rows still contribute revenue.
    per_product_rows = (
        await db.execute(
            select(
                InvoiceLineItem.product_id,
                func.coalesce(Product.name, InvoiceLineItem.description).label("name"),
                func.coalesce(Product.sku, "").label("sku"),
                Product.category,
                Product.purchase_price,
                func.sum(InvoiceLineItem.line_total).label("revenue"),
                func.sum(InvoiceLineItem.quantity).label("qty"),
                func.count(InvoiceLineItem.id).label("lines"),
            )
            .join(Invoice, Invoice.id == InvoiceLineItem.invoice_id)
            .outerjoin(Product, Product.id == InvoiceLineItem.product_id)
            .where(*invoice_filter)
            .group_by(
                InvoiceLineItem.product_id,
                Product.name,
                Product.sku,
                Product.category,
                Product.purchase_price,
                InvoiceLineItem.description,
            )
        )
    ).all()

    products: list[MarginProduct] = []
    total_revenue = Decimal("0")
    total_cogs = Decimal("0")
    total_lines = 0
    by_category_agg: dict[str, dict[str, Decimal]] = {}

    for row in per_product_rows:
        revenue = Decimal(row.revenue or 0)
        qty = Decimal(row.qty or 0)
        unit_cost = Decimal(row.purchase_price or 0)
        cogs = (qty * unit_cost).quantize(Decimal("0.01"))
        gross_profit = (revenue - cogs).quantize(Decimal("0.01"))
        margin_pct = float((gross_profit / revenue) * 100) if revenue > 0 else 0.0

        total_revenue += revenue
        total_cogs += cogs
        total_lines += int(row.lines or 0)

        if row.product_id is not None:
            products.append(MarginProduct(
                product_id=str(row.product_id),
                product_name=row.name or "Unknown",
                sku=row.sku or "",
                category=row.category,
                revenue=revenue.quantize(Decimal("0.01")),
                cogs=cogs,
                gross_profit=gross_profit,
                margin_pct=round(margin_pct, 2),
                quantity_sold=qty,
            ))

        cat_key = (row.category or "uncategorized").lower()
        bucket = by_category_agg.setdefault(
            cat_key,
            {"revenue": Decimal("0"), "cogs": Decimal("0")},
        )
        bucket["revenue"] += revenue
        bucket["cogs"] += cogs

    # Top / bottom products by absolute gross profit. Worst list filters
    # out zero-revenue lines because a stale draft carrying over as 0 SEK
    # isn't useful to flag — the owner wants to see money-losing SKUs
    # with real sales.
    products_with_revenue = [p for p in products if p.revenue > 0]
    top_products = sorted(
        products_with_revenue, key=lambda p: p.gross_profit, reverse=True,
    )[:limit]
    worst_products = sorted(
        products_with_revenue, key=lambda p: p.margin_pct,
    )[:limit]

    total_gross = (total_revenue - total_cogs).quantize(Decimal("0.01"))
    total_margin_pct = float((total_gross / total_revenue) * 100) if total_revenue > 0 else 0.0

    by_category: list[MarginByCategory] = []
    for cat, bucket in sorted(by_category_agg.items()):
        rev = bucket["revenue"].quantize(Decimal("0.01"))
        cogs = bucket["cogs"].quantize(Decimal("0.01"))
        gp = (rev - cogs).quantize(Decimal("0.01"))
        pct = float((gp / rev) * 100) if rev > 0 else 0.0
        by_category.append(MarginByCategory(
            category=cat,
            revenue=rev,
            cogs=cogs,
            gross_profit=gp,
            margin_pct=round(pct, 2),
        ))

    return MarginReport(
        from_date=from_date,
        to_date=to_date,
        overall=MarginOverall(
            revenue=total_revenue.quantize(Decimal("0.01")),
            cogs=total_cogs.quantize(Decimal("0.01")),
            gross_profit=total_gross,
            margin_pct=round(total_margin_pct, 2),
            line_item_count=total_lines,
        ),
        top_products=top_products,
        worst_products=worst_products,
        by_category=by_category,
    )


# ── LTV & churn analytics (Feature 9) ─────────────────────────────────────────

class LtvCustomer(BaseModel):
    customer_id: str
    company_name: str
    total_invoiced: Decimal
    total_paid: Decimal
    invoice_count: int
    first_invoice: date | None
    last_invoice: date | None
    tenure_days: int
    status: str  # "active" | "at_risk" | "churned"


class LtvCohort(BaseModel):
    cohort_month: str           # "2025-01"
    customers: int
    total_revenue: Decimal
    avg_ltv: Decimal


class LtvSummary(BaseModel):
    total_customers: int
    active_customers: int
    at_risk_customers: int
    churned_customers: int
    avg_ltv: Decimal
    median_ltv: Decimal
    churn_rate_pct: float


class LtvReport(BaseModel):
    as_of: date
    active_window_days: int
    at_risk_window_days: int
    summary: LtvSummary
    top_customers: list[LtvCustomer]
    at_risk_customers: list[LtvCustomer]
    cohorts: list[LtvCohort]


@router.get("/ltv", response_model=LtvReport)
async def get_ltv(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    active_window_days: int = Query(60, ge=14, le=365),
    at_risk_window_days: int = Query(120, ge=30, le=540),
    limit: int = Query(10, ge=1, le=50),
    _plan: None = Depends(require_plan(OrgPlan.PRO)),
):
    """Customer LTV + churn classification.

    Status rules (measured against the most recent invoice's issue_date):
      • active:   last_invoice within ``active_window_days`` of today
      • at_risk:  last_invoice within ``at_risk_window_days`` but older
                  than the active window
      • churned:  no invoice within ``at_risk_window_days``

    LTV = ``SUM(total_sek)`` across SENT/PAID/OVERDUE invoices (DRAFT
    excluded because it doesn't represent realised commitment).
    Cohorts bucket customers by the ISO month of their first non-draft
    invoice.
    """
    org_id = _org(ctx)
    today = date.today()
    active_cutoff = today - timedelta(days=active_window_days)
    at_risk_cutoff = today - timedelta(days=at_risk_window_days)

    # Per-customer aggregate. Reuse Payment table for total_paid so
    # "paid" actually reflects collected cash, not invoice status.
    # Payment rows are filtered via Invoice.id to keep the cross-tenant
    # boundary airtight even if a future bug leaks a payment row.
    rows = (
        await db.execute(
            select(
                Customer.id.label("customer_id"),
                Customer.company_name,
                func.coalesce(func.sum(Invoice.total_sek * Invoice.exchange_rate), 0).label("invoiced"),
                func.count(Invoice.id).label("invoice_count"),
                func.min(Invoice.issue_date).label("first_invoice"),
                func.max(Invoice.issue_date).label("last_invoice"),
            )
            .join(Invoice, Invoice.customer_id == Customer.id)
            .where(
                Customer.org_id == org_id,
                Invoice.org_id == org_id,
                Invoice.status.in_([
                    InvoiceStatus.SENT,
                    InvoiceStatus.PAID,
                    InvoiceStatus.OVERDUE,
                ]),
            )
            .group_by(Customer.id, Customer.company_name)
        )
    ).all()

    # Aggregate collected payments in a single query to avoid N+1.
    paid_rows = (
        await db.execute(
            select(
                Invoice.customer_id,
                func.coalesce(func.sum(Payment.amount), 0).label("paid"),
            )
            .join(Payment, Payment.invoice_id == Invoice.id)
            .where(
                Invoice.org_id == org_id,
                Payment.org_id == org_id,
            )
            .group_by(Invoice.customer_id)
        )
    ).all()
    paid_by_customer: dict[uuid.UUID, Decimal] = {
        r.customer_id: Decimal(r.paid or 0) for r in paid_rows
    }

    customers: list[LtvCustomer] = []
    cohorts_agg: dict[str, dict[str, Decimal | int]] = {}

    def _classify(last_inv: date | None) -> str:
        if last_inv is None:
            return "churned"
        if last_inv >= active_cutoff:
            return "active"
        if last_inv >= at_risk_cutoff:
            return "at_risk"
        return "churned"

    for r in rows:
        invoiced = Decimal(r.invoiced or 0)
        paid = paid_by_customer.get(r.customer_id, Decimal("0"))
        first_iv = r.first_invoice
        last_iv = r.last_invoice
        tenure = (today - first_iv).days if first_iv else 0
        status = _classify(last_iv)

        customers.append(LtvCustomer(
            customer_id=str(r.customer_id),
            company_name=r.company_name,
            total_invoiced=invoiced.quantize(Decimal("0.01")),
            total_paid=paid.quantize(Decimal("0.01")),
            invoice_count=int(r.invoice_count or 0),
            first_invoice=first_iv,
            last_invoice=last_iv,
            tenure_days=tenure,
            status=status,
        ))

        if first_iv:
            cohort_key = f"{first_iv.year:04d}-{first_iv.month:02d}"
            bucket = cohorts_agg.setdefault(
                cohort_key,
                {"customers": 0, "total_revenue": Decimal("0")},
            )
            bucket["customers"] = int(bucket["customers"]) + 1
            bucket["total_revenue"] = Decimal(bucket["total_revenue"]) + invoiced

    total_customers = len(customers)
    active = sum(1 for c in customers if c.status == "active")
    at_risk = sum(1 for c in customers if c.status == "at_risk")
    churned = sum(1 for c in customers if c.status == "churned")

    ltvs = sorted(c.total_invoiced for c in customers)
    if ltvs:
        avg_ltv = (sum(ltvs) / len(ltvs)).quantize(Decimal("0.01"))
        mid = len(ltvs) // 2
        median_ltv = (
            ltvs[mid] if len(ltvs) % 2 == 1
            else ((ltvs[mid - 1] + ltvs[mid]) / 2).quantize(Decimal("0.01"))
        )
    else:
        avg_ltv = Decimal("0.00")
        median_ltv = Decimal("0.00")

    # Churn rate: churned ÷ customers-with-any-invoice. If nobody has
    # invoiced we report 0 rather than NaN.
    churn_rate = (churned / total_customers * 100.0) if total_customers > 0 else 0.0

    top_customers = sorted(
        customers, key=lambda c: c.total_invoiced, reverse=True,
    )[:limit]
    at_risk_top = sorted(
        [c for c in customers if c.status == "at_risk"],
        key=lambda c: c.total_invoiced,
        reverse=True,
    )[:limit]

    cohort_list: list[LtvCohort] = []
    for month, bucket in sorted(cohorts_agg.items()):
        count = int(bucket["customers"])
        total_rev = Decimal(bucket["total_revenue"]).quantize(Decimal("0.01"))
        avg = (total_rev / count).quantize(Decimal("0.01")) if count > 0 else Decimal("0.00")
        cohort_list.append(LtvCohort(
            cohort_month=month,
            customers=count,
            total_revenue=total_rev,
            avg_ltv=avg,
        ))

    return LtvReport(
        as_of=today,
        active_window_days=active_window_days,
        at_risk_window_days=at_risk_window_days,
        summary=LtvSummary(
            total_customers=total_customers,
            active_customers=active,
            at_risk_customers=at_risk,
            churned_customers=churned,
            avg_ltv=avg_ltv,
            median_ltv=Decimal(median_ltv).quantize(Decimal("0.01")),
            churn_rate_pct=round(churn_rate, 2),
        ),
        top_customers=top_customers,
        at_risk_customers=at_risk_top,
        cohorts=cohort_list,
    )


# ── PDF export ─────────────────────────────────────────────────────────────────

@router.get("/export/pdf")
async def export_analytics_pdf(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    from_date: date = Query(default=None),
    to_date: date = Query(default=None),
    _plan: None = Depends(require_plan(OrgPlan.PRO)),
):
    """Generate a PDF analytics report for the given date range."""
    from app.models.organization import Organization

    org_id = _org(ctx)
    today = date.today()
    from_date, to_date = _clamp_analytics_range(from_date, to_date)

    # Fetch org name
    org = await db.get(Organization, org_id)
    org_name = org.name if org else "Varuflow"

    # Re-use overview query logic (subset)
    total_invoiced = await db.scalar(
        select(func.coalesce(func.sum(Invoice.total_sek * Invoice.exchange_rate), 0)).where(
            Invoice.org_id == org_id,
            Invoice.issue_date >= from_date,
            Invoice.issue_date <= to_date,
            Invoice.status != InvoiceStatus.DRAFT,
        )
    ) or 0

    total_collected = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount * Payment.exchange_rate), 0)).where(
            Payment.org_id == org_id,
            Payment.payment_date >= from_date,
            Payment.payment_date <= to_date,
        )
    ) or 0

    top_rows = await db.execute(
        select(
            Customer.company_name,
            func.sum(Invoice.total_sek * Invoice.exchange_rate).label("total"),
            func.count(Invoice.id).label("cnt"),
        )
        .join(Customer, Invoice.customer_id == Customer.id)
        .where(
            Invoice.org_id == org_id,
            Invoice.issue_date >= from_date,
            Invoice.issue_date <= to_date,
            Invoice.status != InvoiceStatus.DRAFT,
        )
        .group_by(Customer.company_name)
        .order_by(func.sum(Invoice.total_sek * Invoice.exchange_rate).desc())
        .limit(10)
    )
    top_cust_data = list(top_rows)

    product_rows = await db.execute(
        select(
            InvoiceLineItem.description,
            func.sum(InvoiceLineItem.line_total).label("revenue"),
            func.sum(InvoiceLineItem.quantity).label("qty"),
        )
        .join(Invoice, InvoiceLineItem.invoice_id == Invoice.id)
        .where(
            Invoice.org_id == org_id,
            Invoice.issue_date >= from_date,
            Invoice.issue_date <= to_date,
            Invoice.status != InvoiceStatus.DRAFT,
        )
        .group_by(InvoiceLineItem.description)
        .order_by(func.sum(InvoiceLineItem.line_total).desc())
        .limit(10)
    )
    top_prod_data = list(product_rows)

    # Build PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )
    styles = getSampleStyleSheet()
    story = []

    def cell(text, bold=False, small=False):  # noqa: ARG001
        weight = "b" if bold else ""
        return Paragraph(f"<{weight}>{text}</{weight}>" if weight else text, styles["Normal"])

    # Header — escape org_name because ReportLab parses Paragraph text as
    # mini-XML. An org name containing "<" would otherwise break the PDF.
    from xml.sax.saxutils import escape as _xml_escape
    story.append(Paragraph(f"<b>{_xml_escape(org_name or '')}</b>", styles["Heading1"]))
    story.append(Paragraph(
        f"Analytics Report: {from_date.strftime('%d %b %Y')} – {to_date.strftime('%d %b %Y')}",
        styles["Normal"]
    ))
    story.append(Spacer(1, 8 * mm))

    # Summary KPIs
    summary_data = [
        ["Metric", "Value"],
        ["Total Invoiced", f"{float(total_invoiced):,.0f} SEK"],
        ["Total Collected", f"{float(total_collected):,.0f} SEK"],
        ["Collection Rate", f"{(float(total_collected) / float(total_invoiced) * 100):.1f}%" if total_invoiced else "–"],
    ]
    t = Table(summary_data, colWidths=[80 * mm, 80 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 8 * mm))

    # Top customers
    if top_cust_data:
        story.append(Paragraph("<b>Top Customers by Revenue</b>", styles["Heading3"]))
        story.append(Spacer(1, 3 * mm))
        cust_table = [["Customer", "Invoices", "Revenue (SEK)"]] + [
            [row.company_name, str(row.cnt), f"{float(row.total):,.0f}"]
            for row in top_cust_data
        ]
        ct = Table(cust_table, colWidths=[90 * mm, 30 * mm, 50 * mm])
        ct.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(ct)
        story.append(Spacer(1, 8 * mm))

    # Top products
    if top_prod_data:
        story.append(Paragraph("<b>Top Products by Revenue</b>", styles["Heading3"]))
        story.append(Spacer(1, 3 * mm))
        prod_table = [["Product / Description", "Qty Sold", "Revenue (SEK)"]] + [
            [row.description[:60], f"{float(row.qty):,.1f}", f"{float(row.revenue):,.0f}"]
            for row in top_prod_data
        ]
        pt = Table(prod_table, colWidths=[90 * mm, 30 * mm, 50 * mm])
        pt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(pt)

    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(
        f"<font size='8' color='#6b7280'>Generated {today.strftime('%d %b %Y')} · Varuflow</font>",
        styles["Normal"]
    ))

    doc.build(story)
    pdf_bytes = buffer.getvalue()

    filename = f"analytics-{from_date}-{to_date}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Activity feed (Item 12) ───────────────────────────────────────────────────
# Unified stream of the last N events across invoices, payments, stock
# movements, received POs, and new customers — powers the mobile
# dashboard's Recent Activity card. STARTER+ plan gate.

class ActivityItem(BaseModel):
    type: str  # invoice_created / invoice_paid / stock_movement / purchase_order_received / new_customer
    description: str
    amount_sek: Decimal | None = None
    created_at: str  # ISO-8601 with tz
    icon_hint: str


# Per-org in-memory TTL cache (60 s). Keeps the dashboard snappy without
# adding a Redis dependency. Bounded by tenant count × 1 entry each.
_ACTIVITY_CACHE: dict[tuple[uuid.UUID, int], tuple[float, list[ActivityItem]]] = {}
_ACTIVITY_TTL_SEC = 60.0


def _activity_cache_get(org_id: uuid.UUID, limit: int) -> list[ActivityItem] | None:
    import time
    entry = _ACTIVITY_CACHE.get((org_id, limit))
    if entry is None:
        return None
    expires_at, payload = entry
    if time.monotonic() > expires_at:
        _ACTIVITY_CACHE.pop((org_id, limit), None)
        return None
    return payload


def _activity_cache_set(org_id: uuid.UUID, limit: int, payload: list[ActivityItem]) -> None:
    import time
    _ACTIVITY_CACHE[(org_id, limit)] = (time.monotonic() + _ACTIVITY_TTL_SEC, payload)


@router.get("/activity", response_model=list[ActivityItem])
async def get_activity(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=5, ge=1, le=50),
    _plan: None = Depends(require_plan(OrgPlan.PRO)),
):
    org_id = _org(ctx)
    cached = _activity_cache_get(org_id, limit)
    if cached is not None:
        return cached

    pool: list[tuple[DateTime, ActivityItem]] = []

    # Newest invoices.
    inv_rows = (await db.execute(
        select(Invoice, Customer.company_name)
        .join(Customer, Customer.id == Invoice.customer_id)
        .where(Invoice.org_id == org_id, Invoice.status != InvoiceStatus.DRAFT)
        .order_by(Invoice.created_at.desc())
        .limit(limit)
    )).all()
    for inv, company in inv_rows:
        pool.append((inv.created_at, ActivityItem(
            type="invoice_created",
            description=f"Invoice {inv.invoice_number} — {company}",
            amount_sek=inv.total_sek,
            created_at=inv.created_at.isoformat(),
            icon_hint="file",
        )))

    # Newest payments (invoice_paid).
    pay_rows = (await db.execute(
        select(Payment, Invoice.invoice_number)
        .join(Invoice, Invoice.id == Payment.invoice_id)
        .where(Payment.org_id == org_id)
        .order_by(Payment.created_at.desc())
        .limit(limit)
    )).all()
    for pay, num in pay_rows:
        pool.append((pay.created_at, ActivityItem(
            type="invoice_paid",
            description=f"Payment on {num}",
            amount_sek=pay.amount,
            created_at=pay.created_at.isoformat(),
            icon_hint="check",
        )))

    # Newest stock movements.
    mov_rows = (await db.execute(
        select(StockMovement, Product.name)
        .join(Product, Product.id == StockMovement.product_id)
        .where(StockMovement.org_id == org_id)
        .order_by(StockMovement.created_at.desc())
        .limit(limit)
    )).all()
    for mov, pname in mov_rows:
        pool.append((mov.created_at, ActivityItem(
            type="stock_movement",
            description=f"{mov.type.value} {mov.quantity} × {pname}",
            amount_sek=None,
            created_at=mov.created_at.isoformat(),
            icon_hint="package",
        )))

    # Newest received POs.
    po_rows = (await db.execute(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.org_id == org_id,
            PurchaseOrder.status == PurchaseOrderStatus.RECEIVED,
        )
        .order_by(PurchaseOrder.created_at.desc())
        .limit(limit)
    )).scalars().all()
    for po in po_rows:
        pool.append((po.created_at, ActivityItem(
            type="purchase_order_received",
            description=f"PO received — {po.total} SEK",
            amount_sek=po.total,
            created_at=po.created_at.isoformat(),
            icon_hint="truck",
        )))

    # Newest customers.
    cust_rows = (await db.execute(
        select(Customer)
        .where(Customer.org_id == org_id)
        .order_by(Customer.created_at.desc())
        .limit(limit)
    )).scalars().all()
    for c in cust_rows:
        pool.append((c.created_at, ActivityItem(
            type="new_customer",
            description=f"New customer: {c.company_name}",
            amount_sek=None,
            created_at=c.created_at.isoformat(),
            icon_hint="user-plus",
        )))

    pool.sort(key=lambda pair: pair[0], reverse=True)
    result = [item for _, item in pool[:limit]]
    _activity_cache_set(org_id, limit, result)
    return result


# ── Item 14: Stock-count analytics ───────────────────────────────────────────

class StockCountSummary(BaseModel):
    total: int
    draft: int
    submitted: int
    synced: int
    cancelled: int
    total_positive_variance: int
    total_negative_variance: int
    top_variance: list[dict]


class StockCountVariance(BaseModel):
    count_id: uuid.UUID
    total_expected: int
    total_counted: int
    total_positive: int
    total_negative: int
    items: list[dict]


@router.get("/stock-counts", response_model=StockCountSummary)
async def stock_count_summary(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Org-scoped stock-count overview for the managers dashboard."""
    from app.models.stock_count import StockCount, StockCountItem, StockCountStatus

    org_id = _org(ctx)
    rows = (await db.execute(
        select(StockCount.status, func.count(StockCount.id))
        .where(StockCount.org_id == org_id)
        .group_by(StockCount.status)
    )).all()
    counts_by_status = {str(s.value): n for s, n in rows}

    total = sum(counts_by_status.values())

    pos_row = await db.scalar(
        select(func.coalesce(func.sum(StockCountItem.variance_qty), 0))
        .where(
            StockCountItem.org_id == org_id,
            StockCountItem.variance_qty > 0,
        )
    )
    neg_row = await db.scalar(
        select(func.coalesce(func.sum(StockCountItem.variance_qty), 0))
        .where(
            StockCountItem.org_id == org_id,
            StockCountItem.variance_qty < 0,
        )
    )

    top_rows = (await db.execute(
        select(
            StockCountItem.product_id,
            func.sum(func.abs(StockCountItem.variance_qty)).label("abs_var"),
        )
        .where(
            StockCountItem.org_id == org_id,
            StockCountItem.variance_qty != 0,
        )
        .group_by(StockCountItem.product_id)
        .order_by(func.sum(func.abs(StockCountItem.variance_qty)).desc())
        .limit(5)
    )).all()
    top_variance = [
        {"product_id": str(r.product_id), "abs_variance": int(r.abs_var)}
        for r in top_rows
    ]

    return StockCountSummary(
        total=total,
        draft=counts_by_status.get("DRAFT", 0),
        submitted=counts_by_status.get("SUBMITTED", 0),
        synced=counts_by_status.get("SYNCED", 0),
        cancelled=counts_by_status.get("CANCELLED", 0),
        total_positive_variance=int(pos_row or 0),
        total_negative_variance=int(neg_row or 0),
        top_variance=top_variance,
    )


@router.get("/stock-counts/{count_id}/variance", response_model=StockCountVariance)
async def stock_count_variance(
    count_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Per-item variance breakdown for a single count."""
    from app.models.stock_count import StockCount, StockCountItem

    org_id = _org(ctx)
    sc = await db.scalar(
        select(StockCount).where(
            StockCount.id == count_id, StockCount.org_id == org_id
        )
    )
    if not sc:
        raise HTTPException(status_code=404, detail="Stock count not found")

    rows = (await db.execute(
        select(StockCountItem).where(StockCountItem.stock_count_id == count_id)
    )).scalars().all()

    items = [
        {
            "product_id": str(r.product_id),
            "expected_qty": int(r.expected_qty),
            "counted_qty": int(r.counted_qty),
            "variance_qty": int(r.variance_qty),
        }
        for r in rows
    ]
    return StockCountVariance(
        count_id=count_id,
        total_expected=sum(r.expected_qty for r in rows),
        total_counted=sum(r.counted_qty for r in rows),
        total_positive=sum(r.variance_qty for r in rows if r.variance_qty > 0),
        total_negative=sum(r.variance_qty for r in rows if r.variance_qty < 0),
        items=items,
    )


# ── Auto-reorder analytics (v38 — Item 16) ─────────────────────────────────

class AutoReorderAnalyticsOut(BaseModel):
    total_runs_last_30_days: int
    total_pos_created: int
    products_currently_below_reorder: int
    products_with_auto_reorder_enabled: int
    products_missing_supplier: int
    estimated_reorder_value_sek: Decimal


@router.get("/auto-reorder", response_model=AutoReorderAnalyticsOut)
async def auto_reorder_analytics(
    _: None = Depends(require_plan(OrgPlan.PRO)),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """KPIs for the Settings → Auto-reorder dashboard (PRO+)."""
    from datetime import datetime, timedelta, timezone

    from app.models.auto_reorder import AutoReorderRun
    from app.services.auto_reorder import preview_auto_reorder

    org_id = _org(ctx)
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    # Runs + POs created in the last 30 days.
    row = await db.execute(
        select(
            func.count(AutoReorderRun.id).label("runs"),
            func.coalesce(func.sum(AutoReorderRun.purchase_orders_created), 0).label("pos"),
        ).where(
            AutoReorderRun.org_id == org_id,
            AutoReorderRun.run_at >= cutoff,
        )
    )
    r = row.one()

    # Products currently below reorder_level. Uses the same per-product
    # aggregation the scheduler relies on — cheaper than loading every
    # StockLevel into Python.
    low_subq = (
        select(Product.id)
        .outerjoin(StockLevel, StockLevel.product_id == Product.id)
        .where(
            Product.org_id == org_id,
            Product.is_active == True,  # noqa: E712
            Product.reorder_level > 0,
        )
        .group_by(Product.id, Product.reorder_level)
        .having(
            func.coalesce(func.sum(StockLevel.quantity), 0) <= Product.reorder_level
        )
        .subquery()
    )
    low_count = await db.scalar(select(func.count()).select_from(low_subq)) or 0

    # Products with auto-reorder switched on.
    enabled_count = (
        await db.scalar(
            select(func.count(Product.id)).where(
                Product.org_id == org_id,
                Product.is_active == True,  # noqa: E712
                Product.auto_reorder_enabled == True,  # noqa: E712
            )
        )
        or 0
    )

    # Products that would otherwise be eligible (below reorder, enabled)
    # but have no preferred supplier set — surface so the owner fixes
    # them before the next scheduler tick.
    missing_supplier = (
        await db.scalar(
            select(func.count(Product.id)).where(
                Product.org_id == org_id,
                Product.is_active == True,  # noqa: E712
                Product.auto_reorder_enabled == True,  # noqa: E712
                Product.preferred_supplier_id.is_(None),
                Product.reorder_level > 0,
            )
        )
        or 0
    )

    # Estimated total value of the next run. Reuses the preview service
    # so the dashboard number matches what the owner sees on the
    # "Preview" screen.
    lines = await preview_auto_reorder(db, org_id)
    est_value = sum((l.estimated_cost_sek for l in lines), start=Decimal("0.00"))

    return AutoReorderAnalyticsOut(
        total_runs_last_30_days=int(r.runs),
        total_pos_created=int(r.pos),
        products_currently_below_reorder=int(low_count),
        products_with_auto_reorder_enabled=int(enabled_count),
        products_missing_supplier=int(missing_supplier),
        estimated_reorder_value_sek=est_value,
    )
