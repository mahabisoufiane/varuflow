"""Recurring invoices + auto-overdue marking."""
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_plan
from app.models.invoicing import (
    Customer,
    Invoice,
    InvoiceLineItem,
    InvoiceStatus,
    RecurringFrequency,
    RecurringInvoice,
)
from app.models.organization import OrgPlan

router = APIRouter(
    prefix="/api/recurring",
    tags=["recurring"],
    dependencies=[Depends(require_plan(OrgPlan.PRO))],
)


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Schemas ────────────────────────────────────────────────────────────────────

class RecurringCreate(BaseModel):
    customer_id: uuid.UUID
    frequency: RecurringFrequency
    next_run_date: date
    template_invoice_id: uuid.UUID


class RecurringOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str
    frequency: RecurringFrequency
    next_run_date: date
    is_active: bool
    template_invoice_id: uuid.UUID | None

    model_config = {"from_attributes": True}


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("", response_model=list[RecurringOut])
async def list_recurring(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    result = await db.execute(
        select(RecurringInvoice)
        .options(selectinload(RecurringInvoice.customer))
        .where(RecurringInvoice.org_id == org_id)
        .order_by(RecurringInvoice.next_run_date)
        .offset(skip)
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        RecurringOut(
            id=r.id,
            customer_id=r.customer_id,
            customer_name=r.customer.company_name,
            frequency=r.frequency,
            next_run_date=r.next_run_date,
            is_active=r.is_active,
            template_invoice_id=r.template_invoice_id,
        )
        for r in rows
    ]


@router.post("", response_model=RecurringOut, status_code=status.HTTP_201_CREATED)
async def create_recurring(
    body: RecurringCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)

    customer = await db.scalar(
        select(Customer).where(Customer.id == body.customer_id, Customer.org_id == org_id)
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    template = await db.scalar(
        select(Invoice).where(Invoice.id == body.template_invoice_id, Invoice.org_id == org_id)
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template invoice not found")

    rec = RecurringInvoice(
        org_id=org_id,
        customer_id=body.customer_id,
        frequency=body.frequency,
        next_run_date=body.next_run_date,
        template_invoice_id=body.template_invoice_id,
        is_active=True,
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)

    return RecurringOut(
        id=rec.id,
        customer_id=rec.customer_id,
        customer_name=customer.company_name,
        frequency=rec.frequency,
        next_run_date=rec.next_run_date,
        is_active=rec.is_active,
        template_invoice_id=rec.template_invoice_id,
    )


@router.patch("/{recurring_id}/toggle", response_model=RecurringOut)
async def toggle_recurring(
    recurring_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    result = await db.execute(
        select(RecurringInvoice)
        .options(selectinload(RecurringInvoice.customer))
        .where(RecurringInvoice.id == recurring_id, RecurringInvoice.org_id == org_id)
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Recurring invoice not found")
    rec.is_active = not rec.is_active
    await db.commit()
    await db.refresh(rec)
    return RecurringOut(
        id=rec.id,
        customer_id=rec.customer_id,
        customer_name=rec.customer.company_name,
        frequency=rec.frequency,
        next_run_date=rec.next_run_date,
        is_active=rec.is_active,
        template_invoice_id=rec.template_invoice_id,
    )


@router.post("/{recurring_id}/run", status_code=status.HTTP_201_CREATED)
async def run_now(
    recurring_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger a recurring invoice — creates a new invoice from the template."""
    org_id = _org(ctx)
    result = await db.execute(
        select(RecurringInvoice)
        .options(selectinload(RecurringInvoice.customer))
        .where(RecurringInvoice.id == recurring_id, RecurringInvoice.org_id == org_id)
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    if not rec.is_active:
        raise HTTPException(status_code=422, detail="Recurring invoice is paused")

    # Load template invoice with line items
    tmpl_result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.line_items))
        .where(Invoice.id == rec.template_invoice_id)
    )
    template = tmpl_result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template invoice not found")

    # Count existing to get sequence number
    count = await db.scalar(select(Invoice).where(Invoice.org_id == org_id).with_only_columns(
        __import__("sqlalchemy").func.count()
    )) or 0

    from datetime import datetime
    year = datetime.utcnow().year
    inv_number = f"INV-{year}-{count + 1:04d}"

    today = date.today()
    customer = await db.scalar(select(Customer).where(Customer.id == rec.customer_id))
    due = today + timedelta(days=customer.payment_terms_days if customer else 30)

    new_items = [
        InvoiceLineItem(
            product_id=li.product_id,
            description=li.description,
            quantity=li.quantity,
            unit_price=li.unit_price,
            tax_rate=li.tax_rate,
            line_total=li.line_total,
        )
        for li in template.line_items
    ]

    new_inv = Invoice(
        org_id=org_id,
        customer_id=rec.customer_id,
        invoice_number=inv_number,
        issue_date=today,
        due_date=due,
        status=InvoiceStatus.DRAFT,
        subtotal=template.subtotal,
        vat_amount=template.vat_amount,
        total_sek=template.total_sek,
        notes=template.notes,
        line_items=new_items,
    )
    db.add(new_inv)

    # Advance next_run_date
    if rec.frequency == RecurringFrequency.WEEKLY:
        rec.next_run_date = rec.next_run_date + timedelta(weeks=1)
    else:
        # Monthly — add ~30 days
        m = rec.next_run_date.month + 1
        y = rec.next_run_date.year + (m - 1) // 12
        m = ((m - 1) % 12) + 1
        import calendar
        last_day = calendar.monthrange(y, m)[1]
        rec.next_run_date = rec.next_run_date.replace(
            year=y, month=m, day=min(rec.next_run_date.day, last_day)
        )

    await db.commit()
    return {"status": "created", "invoice_number": inv_number}


# ── Auto-overdue ──────────────────────────────────────────────────────────────

@router.post("/mark-overdue", tags=["invoicing"])
async def mark_overdue(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Mark all past-due SENT invoices as OVERDUE."""
    org_id = _org(ctx)
    today = date.today()
    result = await db.execute(
        select(Invoice).where(
            Invoice.org_id == org_id,
            Invoice.status == InvoiceStatus.SENT,
            Invoice.due_date < today,
        )
    )
    invoices = result.scalars().all()
    for inv in invoices:
        inv.status = InvoiceStatus.OVERDUE
    await db.commit()
    return {"marked": len(invoices)}
