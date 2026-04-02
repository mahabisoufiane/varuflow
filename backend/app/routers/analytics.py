"""Analytics: revenue over time, top customers, inventory value, overdue summary."""
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.inventory import Product, StockLevel, Warehouse
from app.models.invoicing import Customer, Invoice, InvoiceStatus, Payment

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


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
    revenue_12m: list[RevenuePoint]
    top_customers: list[TopCustomer]
    inventory: InventorySummary
    overdue: OverdueSummary


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get("/overview", response_model=AnalyticsOverview)
async def get_overview(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    today = date.today()

    # ── Revenue last 12 months ─────────────────────────────────────────────
    revenue_points: list[RevenuePoint] = []
    for i in range(11, -1, -1):
        # first day of month i months ago
        first = (today.replace(day=1) - timedelta(days=i * 28)).replace(day=1)
        if first.month == 12:
            last = first.replace(year=first.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            last = first.replace(month=first.month + 1, day=1) - timedelta(days=1)

        invoiced_result = await db.scalar(
            select(func.coalesce(func.sum(Invoice.total_sek), 0)).where(
                Invoice.org_id == org_id,
                Invoice.issue_date >= first,
                Invoice.issue_date <= last,
                Invoice.status != InvoiceStatus.DRAFT,
            )
        )
        collected_result = await db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.org_id == org_id,
                Payment.payment_date >= first,
                Payment.payment_date <= last,
            )
        )
        revenue_points.append(RevenuePoint(
            month=first.strftime("%Y-%m"),
            invoiced=Decimal(str(invoiced_result)),
            collected=Decimal(str(collected_result)),
        ))

    # ── Top 5 customers by total invoiced ─────────────────────────────────
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

    # ── Inventory summary ──────────────────────────────────────────────────
    product_count = await db.scalar(
        select(func.count()).where(Product.org_id == org_id, Product.is_active == True)
    ) or 0

    warehouse_count = await db.scalar(
        select(func.count()).where(Warehouse.org_id == org_id, Warehouse.is_active == True)
    ) or 0

    stock_rows = await db.execute(
        select(StockLevel, Product)
        .join(Product, StockLevel.product_id == Product.id)
        .where(Product.org_id == org_id, Product.is_active == True)
    )
    stock_value = Decimal("0.00")
    low_stock = 0
    for sl, p in stock_rows:
        stock_value += Decimal(str(sl.quantity)) * p.purchase_price
        if sl.quantity <= sl.min_threshold:
            low_stock += 1

    # ── Overdue summary ────────────────────────────────────────────────────
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
        revenue_12m=revenue_points,
        top_customers=top_customers,
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
