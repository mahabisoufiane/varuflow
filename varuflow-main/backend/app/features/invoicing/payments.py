"""Invoicing routes: payments, aging report, installment plans."""
import logging
import uuid
from datetime import date
from decimal import Decimal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from .models import (
    Invoice,
    InvoiceStatus,
    Payment,
)
from .schemas import (
    AgingBucket,
    AgingReport,
    PaymentCreate,
    PaymentOut,
)

from ._shared import (
    _org,
)

log = logging.getLogger(__name__)
router = APIRouter()


# ── Payments ──────────────────────────────────────────────────────────────────

@router.get("/invoices/{invoice_id}/payments")
async def list_payments(
    invoice_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    inv = await db.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.org_id == org_id)
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    base = select(Payment).where(Payment.invoice_id == invoice_id)
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    result = await db.execute(
        base.order_by(Payment.payment_date)
        .offset((page - 1) * limit)
        .limit(limit)
    )
    items = result.scalars().all()
    total_pages = max(1, -(-total // limit))
    return {
        "items": items,
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


@router.post(
    "/invoices/{invoice_id}/payments",
    response_model=PaymentOut,
    status_code=status.HTTP_201_CREATED,
)
async def record_payment(
    invoice_id: uuid.UUID,
    body: PaymentCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    # Lock the invoice row to serialise concurrent payment inserts and prevent
    # two racing requests from both exceeding the balance.
    inv = await db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.org_id == org_id)
        .with_for_update()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status == InvoiceStatus.DRAFT:
        raise HTTPException(status_code=422, detail="Cannot record payment on a DRAFT invoice")

    # Sanity-check the payment date. Pydantic only enforces the type, so
    # without these guards an operator typo ("2099-12-31") or a client
    # bug can flip an invoice to PAID in a VAT period that hasn't
    # happened yet (analytics exports and reconciliations will then
    # disagree with the cashbook), and a pre-issue payment date breaks
    # the chronology required by Swedish bokföringslagen 5 kap. 6 §.
    today = date.today()
    if body.payment_date > today:
        raise HTTPException(
            status_code=422,
            detail="Payment date cannot be in the future.",
        )
    if body.payment_date < inv.issue_date:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Payment date {body.payment_date} is before the invoice "
                f"issue date {inv.issue_date}."
            ),
        )

    # Check existing payments BEFORE inserting the new one so we can reject
    # over-payments that would drive the outstanding balance negative.
    existing_paid_result = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.invoice_id == invoice_id
        )
    )
    existing_paid = Decimal(str(existing_paid_result or 0))
    new_total = existing_paid + body.amount
    if new_total > inv.total_sek:
        remaining = inv.total_sek - existing_paid
        raise HTTPException(
            status_code=422,
            detail=(
                f"Payment exceeds invoice balance "
                f"({remaining} SEK remaining). "
                "Record a credit note instead."
            ),
        )

    payment = Payment(
        org_id=org_id,
        invoice_id=invoice_id,
        **body.model_dump(),
    )
    db.add(payment)

    # Auto-mark PAID if payment covers full amount
    if new_total >= inv.total_sek:
        inv.status = InvoiceStatus.PAID

    await db.commit()
    await db.refresh(payment)
    return payment



# ── Aging report ──────────────────────────────────────────────────────────────

@router.get("/aging", response_model=AgingReport)
async def aging_report(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    today = date.today()

    # Cap the report at a sane upper bound so a tenant with tens of thousands
    # of outstanding invoices cannot OOM the API process.
    AGING_MAX_INVOICES = 5000

    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.customer))
        .where(
            Invoice.org_id == org_id,
            Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE]),
        )
        .order_by(Invoice.due_date.asc())
        .limit(AGING_MAX_INVOICES)
    )
    invoices = result.scalars().all()

    # Sum payments per invoice in a single grouped query so the aging bucket
    # reflects the true outstanding balance (gross − paid) rather than the
    # invoice gross. Partially-paid invoices were previously inflating totals.
    paid_by_invoice: dict[uuid.UUID, Decimal] = {}
    if invoices:
        inv_ids = [inv.id for inv in invoices]
        pay_rows = await db.execute(
            select(Payment.invoice_id, func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.invoice_id.in_(inv_ids))
            .group_by(Payment.invoice_id)
        )
        for inv_id, total in pay_rows.all():
            paid_by_invoice[inv_id] = Decimal(str(total or 0))

    buckets: dict[str, list[AgingBucket]] = {
        "current": [],
        "days_1_30": [],
        "days_31_60": [],
        "days_61_90": [],
        "days_90_plus": [],
    }
    total_outstanding = Decimal("0.00")

    for inv in invoices:
        paid = paid_by_invoice.get(inv.id, Decimal("0"))
        outstanding = inv.total_sek - paid
        # Skip fully-paid invoices that haven't been marked PAID yet (edge
        # case — should be rare now that record_payment auto-marks PAID).
        if outstanding <= 0:
            continue
        days_overdue = (today - inv.due_date).days
        bucket = AgingBucket(
            customer=inv.customer.company_name,
            invoice_number=inv.invoice_number,
            invoice_id=inv.id,
            total_sek=outstanding,
            due_date=inv.due_date,
            days_overdue=max(0, days_overdue),
        )
        total_outstanding += outstanding
        if days_overdue <= 0:
            buckets["current"].append(bucket)
        elif days_overdue <= 30:
            buckets["days_1_30"].append(bucket)
        elif days_overdue <= 60:
            buckets["days_31_60"].append(bucket)
        elif days_overdue <= 90:
            buckets["days_61_90"].append(bucket)
        else:
            buckets["days_90_plus"].append(bucket)

    return AgingReport(**buckets, total_outstanding=total_outstanding)



# ── Invoice Installment Plans ───────────────────────────────────────────────


@router.post("/invoices/{invoice_id}/installments", status_code=status.HTTP_201_CREATED)
async def create_installment_plan(
    invoice_id: uuid.UUID,
    parts: int = 4,
    interval_days: int = 30,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Create an installment plan for an invoice."""
    from app.features.compliance.audit_models import AuditLogEntry
    from app.features.invoicing.invoice_installment import InvoiceInstallment
    from app.services.invoice_installment import build_plan

    org_id = _org(ctx)
    user_id = ctx[0]

    try:
        result = await db.execute(
            select(Invoice).where(Invoice.id == invoice_id, Invoice.org_id == org_id)
        )
        inv = result.scalar_one_or_none()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")

        plan = build_plan(
            total_sek=inv.total_sek,
            parts=parts,
            start_date=inv.due_date,
            interval_days=interval_days,
        )

        rows = []
        for p in plan:
            row = InvoiceInstallment(
                org_id=org_id,
                invoice_id=invoice_id,
                sequence=p.sequence,
                amount_sek=p.amount_sek,
                due_date=p.due_date,
                status="scheduled",
            )
            db.add(row)
            rows.append(row)

        db.add(AuditLogEntry(
            org_id=org_id,
            actor_user_id=user_id,
            action="invoice_installment.plan_created",
            target_type="invoice",
            target_id=str(invoice_id),
            extra={"parts": parts, "interval_days": interval_days},
        ))

        await db.commit()
        return {"invoice_id": str(invoice_id), "installments": len(rows)}

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_installment_plan failed: {str(e)}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/installments/{installment_id}/payments", status_code=status.HTTP_200_OK)
async def record_installment_payment(
    installment_id: uuid.UUID,
    payment_sek: Decimal,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Record a payment against a single installment."""
    from app.features.compliance.audit_models import AuditLogEntry
    from app.features.invoicing.invoice_installment import InvoiceInstallment
    from app.services.invoice_installment import apply_payment

    org_id = _org(ctx)
    user_id = ctx[0]

    try:
        result = await db.execute(
            select(InvoiceInstallment).where(
                InvoiceInstallment.id == installment_id,
                InvoiceInstallment.org_id == org_id,
            )
        )
        inst = result.scalar_one_or_none()
        if not inst:
            raise HTTPException(status_code=404, detail="Installment not found")

        new_paid, new_status = apply_payment(
            paid_amount_sek=inst.paid_amount_sek or Decimal("0.00"),
            amount_sek=inst.amount_sek,
            payment_sek=payment_sek,
        )
        inst.paid_amount_sek = new_paid
        inst.status = new_status

        db.add(AuditLogEntry(
            org_id=org_id,
            actor_user_id=user_id,
            action="invoice_installment.payment_recorded",
            target_type="invoice_installment",
            target_id=str(installment_id),
            extra={"payment_sek": str(payment_sek), "new_status": new_status},
        ))

        await db.commit()
        return {"installment_id": str(installment_id), "paid": str(new_paid), "status": new_status}

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"record_installment_payment failed: {str(e)}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/invoices/{invoice_id}/installments", status_code=status.HTTP_200_OK)
async def cancel_installment_plan(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Cancel all unpaid installments for an invoice."""
    from app.features.compliance.audit_models import AuditLogEntry
    from app.features.invoicing.invoice_installment import InvoiceInstallment

    org_id = _org(ctx)
    user_id = ctx[0]

    try:
        result = await db.execute(
            select(InvoiceInstallment).where(
                InvoiceInstallment.invoice_id == invoice_id,
                InvoiceInstallment.org_id == org_id,
                InvoiceInstallment.status.in_(["scheduled", "partial", "overdue"]),
            )
        )
        rows = result.scalars().all()
        for row in rows:
            row.status = "cancelled"

        db.add(AuditLogEntry(
            org_id=org_id,
            actor_user_id=user_id,
            action="invoice_installment.plan_cancelled",
            target_type="invoice",
            target_id=str(invoice_id),
            extra={"cancelled_count": len(rows)},
        ))

        await db.commit()
        return {"invoice_id": str(invoice_id), "cancelled": len(rows)}

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"cancel_installment_plan failed: {str(e)}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
