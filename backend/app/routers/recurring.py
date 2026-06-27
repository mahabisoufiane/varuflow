"""Recurring invoices + auto-overdue marking."""
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, update
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

# A second router mounted under the same /api/recurring prefix for endpoints
# that should NOT be plan-gated. The "mark-overdue" sweep is a basic
# invoicing housekeeping operation and FREE-tier users have an invoices
# page button that calls it — gating it behind PRO produced a 402 every
# time a FREE user clicked "Mark overdue" in the invoices page header.
public_router = APIRouter(prefix="/api/recurring", tags=["invoicing"])


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
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    result = await db.execute(
        select(RecurringInvoice)
        .options(selectinload(RecurringInvoice.customer))
        .where(RecurringInvoice.org_id == org_id)
        .order_by(RecurringInvoice.next_run_date)
        .limit(limit)
        .offset(offset)
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
    # Mirror the guard in POST /invoices and POST /recurring/{id}/run.
    # Without this, a merchant can create a brand-new recurring schedule
    # against an already-archived customer (is_active=False) — the
    # schedule is then a permanent dead-letter: run_now refuses to fire,
    # but the recurring row keeps showing up in the UI list with no
    # indication why it never runs. Refuse at creation time so the
    # merchant gets immediate feedback.
    if not customer.is_active:
        raise HTTPException(
            status_code=422,
            detail="Customer is archived — reactivate before creating a recurring schedule.",
        )

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
    # Lock the RecurringInvoice row so two concurrent /run requests for the
    # same recurring_id don't both create an invoice while only advancing
    # next_run_date once — that would silently double-bill the customer.
    result = await db.execute(
        select(RecurringInvoice)
        .options(selectinload(RecurringInvoice.customer))
        .where(RecurringInvoice.id == recurring_id, RecurringInvoice.org_id == org_id)
        .with_for_update()
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    if not rec.is_active:
        raise HTTPException(status_code=422, detail="Recurring invoice is paused")

    # Load template invoice with line items — scope to caller's org so a
    # corrupted/tampered template_invoice_id cannot pull another org's data.
    tmpl_result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.line_items))
        .where(
            Invoice.id == rec.template_invoice_id,
            Invoice.org_id == org_id,
        )
    )
    template = tmpl_result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template invoice not found")

    # Generate invoice number from max-existing-sequence.
    #
    # Serialize on the Organization row first so two simultaneous /run
    # calls don't both produce INV-YYYY-(N+1). Combined with the DB-level
    # UNIQUE(org_id, invoice_number) constraint (migration v15) this
    # guarantees monotonic, gap-free, non-reusable numbering per-tenant
    # as required by Swedish bokföringslagen (BFL). Using MAX(sequence)
    # instead of COUNT(*) so deleting a DRAFT invoice cannot reuse its
    # number.
    from app.models.organization import Organization as _Org
    from sqlalchemy import func as _sqlfunc
    await db.execute(
        select(_Org.id).where(_Org.id == org_id).with_for_update()
    )
    from datetime import datetime, timezone
    year = datetime.now(timezone.utc).year
    year_prefix = f"INV-{year}-"
    max_row = await db.scalar(
        select(_sqlfunc.max(Invoice.invoice_number))
        .where(
            Invoice.org_id == org_id,
            Invoice.invoice_number.like(f"{year_prefix}%"),
        )
    )
    next_seq = 1
    if max_row:
        try:
            next_seq = int(max_row.rsplit("-", 1)[-1]) + 1
        except (ValueError, IndexError):
            next_seq = 1
    inv_number = f"INV-{year}-{next_seq:04d}"

    today = date.today()
    customer = await db.scalar(
        select(Customer).where(
            Customer.id == rec.customer_id,
            Customer.org_id == org_id,
        )
    )
    # If the merchant archived the customer (DELETE /customers/{id} →
    # is_active=False) the recurring schedule was left in place and
    # would silently keep minting DRAFT invoices on every /run click,
    # all addressed to an archived counterparty. Pause-or-fail here so
    # the merchant has to consciously re-activate the customer (or
    # pause/delete the recurring) before another invoice is cut.
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not customer.is_active:
        raise HTTPException(
            status_code=422,
            detail="Customer is archived — reactivate or pause the recurring schedule.",
        )
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

# Mounted on `public_router` (no plan gate). The invoices page in the
# FREE plan dashboard has a "Mark overdue" button that calls this — it must
# be reachable without PRO or those users get a 402 on every click.
@public_router.post("/mark-overdue", tags=["invoicing"])
async def mark_overdue(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Mark all past-due SENT invoices as OVERDUE."""
    org_id = _org(ctx)
    today = date.today()
    # Use an atomic bulk UPDATE keyed on (org_id, status=SENT, due_date<today)
    # instead of SELECT → loop → commit. The loop pattern had a TOCTOU race:
    # a concurrent record_payment() flipping an invoice to PAID between the
    # SELECT and the COMMIT was silently overwritten back to OVERDUE, which
    # corrupts the BFL audit trail (payment already logged, invoice now
    # shows OVERDUE). The WHERE clause in a single UPDATE re-evaluates
    # status at write time, so rows that moved to PAID in the interim are
    # skipped. Also O(1) round-trip regardless of overdue count.
    result = await db.execute(
        update(Invoice)
        .where(
            Invoice.org_id == org_id,
            Invoice.status == InvoiceStatus.SENT,
            Invoice.due_date < today,
        )
        .values(status=InvoiceStatus.OVERDUE)
        .execution_options(synchronize_session=False)
    )
    await db.commit()
    return {"marked": result.rowcount or 0}
