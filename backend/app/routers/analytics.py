"""Analytics: revenue over time, top customers, top products, inventory value, overdue summary."""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
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
from app.models.inventory import Product, StockLevel, Warehouse
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


class OverdueSummary(BaseModel):
    overdue_count: int
    overdue_total: Decimal
    oldest_days: int


class AnalyticsOverview(BaseModel):
    from_date: date
    to_date: date
    revenue_points: list[RevenuePoint]
    top_customers: list[TopCustomer]
    top_products: list[TopProduct]
    status_breakdown: list[StatusBucket]
    inventory: InventorySummary
    overdue: OverdueSummary


# ── Helpers ───────────────────────────────────────────────────────────────────

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
):
    org_id = _org(ctx)
    today = date.today()

    if to_date is None:
        to_date = today
    if from_date is None:
        from_date = (today.replace(day=1) - timedelta(days=11 * 28)).replace(day=1)

    # ── Revenue by month ───────────────────────────────────────────────────
    revenue_points: list[RevenuePoint] = []
    for first, last in _month_range(from_date, to_date):
        invoiced = await db.scalar(
            select(func.coalesce(func.sum(Invoice.total_sek), 0)).where(
                Invoice.org_id == org_id,
                Invoice.issue_date >= first,
                Invoice.issue_date <= last,
                Invoice.status != InvoiceStatus.DRAFT,
            )
        )
        collected = await db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.org_id == org_id,
                Payment.payment_date >= first,
                Payment.payment_date <= last,
            )
        )
        revenue_points.append(RevenuePoint(
            month=first.strftime("%Y-%m"),
            invoiced=Decimal(str(invoiced)),
            collected=Decimal(str(collected)),
        ))

    # ── Top customers ──────────────────────────────────────────────────────
    top_rows = await db.execute(
        select(
            Invoice.customer_id,
            Customer.company_name,
            func.sum(Invoice.total_sek).label("total_invoiced"),
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
        .order_by(func.sum(Invoice.total_sek).desc())
        .limit(5)
    )
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
            func.coalesce(func.sum(Invoice.total_sek), 0).label("total"),
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
    stock_rows = await db.execute(
        select(StockLevel, Product)
        .join(Product, StockLevel.product_id == Product.id)
        .where(Product.org_id == org_id, Product.is_active == True)  # noqa: E712
    )
    stock_value = Decimal("0.00")
    low_stock = 0
    for sl, p in stock_rows:
        stock_value += Decimal(str(sl.quantity)) * p.purchase_price
        if sl.quantity <= sl.min_threshold:
            low_stock += 1

    # ── Overdue ────────────────────────────────────────────────────────────
    overdue_rows = await db.execute(
        select(Invoice).where(
            Invoice.org_id == org_id,
            Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE]),
            Invoice.due_date < today,
        )
    )
    overdue_invoices = overdue_rows.scalars().all()
    overdue_total = sum(i.total_sek for i in overdue_invoices)
    oldest_days = max(((today - i.due_date).days for i in overdue_invoices), default=0)

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
        ),
        overdue=OverdueSummary(
            overdue_count=len(overdue_invoices),
            overdue_total=Decimal(str(overdue_total)),
            oldest_days=oldest_days,
        ),
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
    if to_date is None:
        to_date = today
    if from_date is None:
        from_date = (today.replace(day=1) - timedelta(days=11 * 28)).replace(day=1)

    # Fetch org name
    org = await db.get(Organization, org_id)
    org_name = org.name if org else "Varuflow"

    # Re-use overview query logic (subset)
    total_invoiced = await db.scalar(
        select(func.coalesce(func.sum(Invoice.total_sek), 0)).where(
            Invoice.org_id == org_id,
            Invoice.issue_date >= from_date,
            Invoice.issue_date <= to_date,
            Invoice.status != InvoiceStatus.DRAFT,
        )
    ) or 0

    total_collected = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.org_id == org_id,
            Payment.payment_date >= from_date,
            Payment.payment_date <= to_date,
        )
    ) or 0

    top_rows = await db.execute(
        select(
            Customer.company_name,
            func.sum(Invoice.total_sek).label("total"),
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
        .order_by(func.sum(Invoice.total_sek).desc())
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

    # Header
    story.append(Paragraph(f"<b>{org_name}</b>", styles["Heading1"]))
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
