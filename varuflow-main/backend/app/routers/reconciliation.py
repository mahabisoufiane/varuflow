"""Payment Reconciliation Dashboard router.

GET  /api/reconciliation                — all payments with invoice match status
GET  /api/reconciliation/summary        — daily/monthly summary stats
GET  /api/reconciliation/unmatched      — invoices with no payments (unmatched)
GET  /api/reconciliation/partial        — invoices with partial payments
GET  /api/reconciliation/overpaid       — invoices where amount_paid > total
GET  /api/reconciliation/by-method      — payments grouped by method
"""
import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.invoicing import Invoice, Payment

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reconciliation", tags=["reconciliation"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _payment_out(p: Payment) -> dict:
    return {
        "id": str(p.id),
        "invoice_id": str(p.invoice_id),
        "amount": float(p.amount),
        "currency": p.currency,
        "payment_date": p.payment_date.isoformat(),
        "method": p.method.value if hasattr(p.method, "value") else str(p.method),
        "reference": p.reference,
    }


# ── Overview — all payments ───────────────────────────────────────────────────

@router.get("")
async def list_reconciled_payments(
    method: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 100,
    offset: int = 0,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """All payments with their invoice match status."""
    try:
        org_id = member["org_id"]
        q = select(Payment, Invoice).join(
            Invoice, Payment.invoice_id == Invoice.id
        ).where(Payment.org_id == org_id)

        if method:
            q = q.where(Payment.method == method)
        if from_date:
            q = q.where(Payment.payment_date >= date.fromisoformat(from_date))
        if to_date:
            q = q.where(Payment.payment_date <= date.fromisoformat(to_date))

        q = q.order_by(Payment.payment_date.desc()).limit(limit).offset(offset)
        rows = (await db.execute(q)).all()

        result = []
        for payment, invoice in rows:
            total = float(invoice.total_amount or 0)
            paid = float(invoice.amount_paid or 0)
            if paid >= total:
                match_status = "matched"
            elif paid > 0:
                match_status = "partial"
            else:
                match_status = "unmatched"
            overpaid = max(0.0, paid - total)

            result.append({
                **_payment_out(payment),
                "invoice_number": invoice.invoice_number,
                "invoice_status": invoice.status,
                "invoice_total": total,
                "invoice_amount_paid": paid,
                "invoice_outstanding": max(0.0, total - paid),
                "match_status": match_status,
                "overpaid": overpaid,
            })

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("reconciliation list failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Summary stats ─────────────────────────────────────────────────────────────

@router.get("/summary")
async def reconciliation_summary(
    period: str = "month",   # today | week | month | year
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Reconciliation summary for a time period."""
    try:
        org_id = member["org_id"]
        today = date.today()
        if period == "today":
            from_d = today
        elif period == "week":
            from_d = today - timedelta(days=7)
        elif period == "year":
            from_d = today.replace(month=1, day=1)
        else:  # month
            from_d = today.replace(day=1)

        # Total received in period
        total_received = await db.scalar(
            select(func.sum(Payment.amount)).where(
                Payment.org_id == org_id,
                Payment.payment_date >= from_d,
            )
        ) or 0

        # Payment count
        payment_count = await db.scalar(
            select(func.count()).where(
                Payment.org_id == org_id,
                Payment.payment_date >= from_d,
            )
        ) or 0

        # By method breakdown
        method_rows = (await db.execute(
            select(Payment.method, func.sum(Payment.amount), func.count())
            .where(Payment.org_id == org_id, Payment.payment_date >= from_d)
            .group_by(Payment.method)
        )).all()

        by_method = [
            {
                "method": r[0].value if hasattr(r[0], "value") else str(r[0]),
                "total": float(r[1] or 0),
                "count": r[2],
            }
            for r in method_rows
        ]

        # Unmatched invoices (status not PAID, no payments)
        unmatched_count = await db.scalar(
            select(func.count()).where(
                Invoice.org_id == org_id,
                Invoice.status.notin_(["PAID", "CANCELLED", "VOID", "DRAFT"]),
                Invoice.amount_paid == 0,
            )
        ) or 0

        # Partial invoices
        partial_count = await db.scalar(
            select(func.count()).where(
                Invoice.org_id == org_id,
                Invoice.status.notin_(["PAID", "CANCELLED", "VOID"]),
                Invoice.amount_paid > 0,
                Invoice.amount_paid < Invoice.total_amount,
            )
        ) or 0

        # Overpaid invoices
        overpaid_count = await db.scalar(
            select(func.count()).where(
                Invoice.org_id == org_id,
                Invoice.amount_paid > Invoice.total_amount,
            )
        ) or 0

        return {
            "period": period,
            "from_date": from_d.isoformat(),
            "to_date": today.isoformat(),
            "total_received": float(total_received),
            "payment_count": payment_count,
            "unmatched_invoices": unmatched_count,
            "partial_invoices": partial_count,
            "overpaid_invoices": overpaid_count,
            "by_method": by_method,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("reconciliation_summary failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Unmatched invoices ────────────────────────────────────────────────────────

@router.get("/unmatched")
async def unmatched_invoices(
    limit: int = 50,
    offset: int = 0,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Invoices expecting payment but with no payments recorded."""
    try:
        org_id = member["org_id"]
        rows = (await db.execute(
            select(Invoice)
            .where(
                Invoice.org_id == org_id,
                Invoice.status.notin_(["PAID", "CANCELLED", "VOID", "DRAFT"]),
                Invoice.amount_paid == 0,
            )
            .order_by(Invoice.due_date.asc().nullslast())
            .limit(limit).offset(offset)
        )).scalars().all()

        return [
            {
                "id": str(inv.id),
                "invoice_number": inv.invoice_number,
                "customer_id": str(inv.customer_id) if inv.customer_id else None,
                "total_amount": float(inv.total_amount or 0),
                "currency": inv.currency,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "status": inv.status,
                "days_overdue": max(0, (date.today() - inv.due_date).days) if inv.due_date and inv.due_date < date.today() else 0,
            }
            for inv in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("unmatched_invoices failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Partial payments ──────────────────────────────────────────────────────────

@router.get("/partial")
async def partial_invoices(
    limit: int = 50,
    offset: int = 0,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Invoices with partial payments — outstanding balance > 0."""
    try:
        org_id = member["org_id"]
        rows = (await db.execute(
            select(Invoice)
            .where(
                Invoice.org_id == org_id,
                Invoice.status.notin_(["PAID", "CANCELLED", "VOID"]),
                Invoice.amount_paid > 0,
                Invoice.amount_paid < Invoice.total_amount,
            )
            .order_by(Invoice.due_date.asc().nullslast())
            .limit(limit).offset(offset)
        )).scalars().all()

        return [
            {
                "id": str(inv.id),
                "invoice_number": inv.invoice_number,
                "customer_id": str(inv.customer_id) if inv.customer_id else None,
                "total_amount": float(inv.total_amount or 0),
                "amount_paid": float(inv.amount_paid or 0),
                "outstanding": float((inv.total_amount or 0) - (inv.amount_paid or 0)),
                "currency": inv.currency,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "status": inv.status,
            }
            for inv in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("partial_invoices failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Overpaid invoices ─────────────────────────────────────────────────────────

@router.get("/overpaid")
async def overpaid_invoices(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Invoices where total payments exceed the invoice total."""
    try:
        org_id = member["org_id"]
        rows = (await db.execute(
            select(Invoice)
            .where(
                Invoice.org_id == org_id,
                Invoice.amount_paid > Invoice.total_amount,
            )
            .order_by(Invoice.updated_at.desc())
        )).scalars().all()

        return [
            {
                "id": str(inv.id),
                "invoice_number": inv.invoice_number,
                "customer_id": str(inv.customer_id) if inv.customer_id else None,
                "total_amount": float(inv.total_amount or 0),
                "amount_paid": float(inv.amount_paid or 0),
                "overpaid_by": float((inv.amount_paid or 0) - (inv.total_amount or 0)),
                "currency": inv.currency,
            }
            for inv in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("overpaid_invoices failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Payment method breakdown ──────────────────────────────────────────────────

@router.get("/by-method")
async def payments_by_method(
    from_date: str | None = None,
    to_date: str | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = (
            select(Payment.method, Payment.currency, func.sum(Payment.amount), func.count())
            .where(Payment.org_id == org_id)
        )
        if from_date:
            q = q.where(Payment.payment_date >= date.fromisoformat(from_date))
        if to_date:
            q = q.where(Payment.payment_date <= date.fromisoformat(to_date))
        q = q.group_by(Payment.method, Payment.currency)

        rows = (await db.execute(q)).all()
        return [
            {
                "method": r[0].value if hasattr(r[0], "value") else str(r[0]),
                "currency": r[1],
                "total": float(r[2] or 0),
                "count": r[3],
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("payments_by_method failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")
