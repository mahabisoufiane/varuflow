"""Payment Reconciliation Dashboard router.

GET  /api/reconciliation                — all payments with invoice match status
GET  /api/reconciliation/summary        — daily/monthly summary stats
GET  /api/reconciliation/unmatched      — invoices with no payments (unmatched)
GET  /api/reconciliation/partial        — invoices with partial payments
GET  /api/reconciliation/overpaid       — invoices where amount_paid > total
GET  /api/reconciliation/by-method      — payments grouped by method
"""
import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module, require_role
from app.features.invoicing.models import Invoice, Payment
from app.features.auth.organization import OrgRole

logger = logging.getLogger(__name__)
# Reconciliation is manager-level finance work — gate at ADMIN.
router = APIRouter(prefix="/api/reconciliation", tags=["reconciliation"], dependencies=[Depends(require_module("finance")), Depends(require_role(OrgRole.ADMIN))])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _paid_subq():
    """Correlated subquery: sum of all payments received against an invoice."""
    return (
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(Payment.invoice_id == Invoice.id)
        .correlate(Invoice)
        .scalar_subquery()
    )


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
        paid_col = _paid_subq().label("total_paid")
        q = (
            select(Payment, Invoice, paid_col)
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .where(Payment.org_id == org_id)
        )

        if method:
            q = q.where(Payment.method == method)
        if from_date:
            q = q.where(Payment.payment_date >= date.fromisoformat(from_date))
        if to_date:
            q = q.where(Payment.payment_date <= date.fromisoformat(to_date))

        q = q.order_by(Payment.payment_date.desc()).limit(limit).offset(offset)
        rows = (await db.execute(q)).all()

        result = []
        for payment, invoice, total_paid in rows:
            total = float(invoice.total_sek or 0)
            paid = float(total_paid or 0)
            if paid >= total and total > 0:
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
            select(func.count()).select_from(Payment).where(
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

        # Use paid subquery for per-invoice aggregate counts
        paid_subq = _paid_subq()

        unmatched_count = await db.scalar(
            select(func.count()).select_from(Invoice).where(
                Invoice.org_id == org_id,
                Invoice.status.notin_(["PAID", "DRAFT"]),
                paid_subq == 0,
            )
        ) or 0

        partial_count = await db.scalar(
            select(func.count()).select_from(Invoice).where(
                Invoice.org_id == org_id,
                Invoice.status.notin_(["PAID"]),
                paid_subq > 0,
                paid_subq < Invoice.total_sek,
            )
        ) or 0

        overpaid_count = await db.scalar(
            select(func.count()).select_from(Invoice).where(
                Invoice.org_id == org_id,
                paid_subq > Invoice.total_sek,
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
        paid_subq = _paid_subq()
        rows = (await db.execute(
            select(Invoice)
            .where(
                Invoice.org_id == org_id,
                Invoice.status.notin_(["PAID", "DRAFT"]),
                paid_subq == 0,
            )
            .order_by(Invoice.due_date.asc().nullslast())
            .limit(limit).offset(offset)
        )).scalars().all()

        return [
            {
                "id": str(inv.id),
                "invoice_number": inv.invoice_number,
                "customer_id": str(inv.customer_id) if inv.customer_id else None,
                "total_amount": float(inv.total_sek or 0),
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
        paid_subq = _paid_subq()
        paid_col = paid_subq.label("amount_paid")
        rows = (await db.execute(
            select(Invoice, paid_col)
            .where(
                Invoice.org_id == org_id,
                Invoice.status.notin_(["PAID"]),
                paid_subq > 0,
                paid_subq < Invoice.total_sek,
            )
            .order_by(Invoice.due_date.asc().nullslast())
            .limit(limit).offset(offset)
        )).all()

        return [
            {
                "id": str(inv.id),
                "invoice_number": inv.invoice_number,
                "customer_id": str(inv.customer_id) if inv.customer_id else None,
                "total_amount": float(inv.total_sek or 0),
                "amount_paid": float(paid or 0),
                "outstanding": float((inv.total_sek or 0) - (paid or 0)),
                "currency": inv.currency,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "status": inv.status,
            }
            for inv, paid in rows
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
        paid_subq = _paid_subq()
        paid_col = paid_subq.label("amount_paid")
        rows = (await db.execute(
            select(Invoice, paid_col)
            .where(
                Invoice.org_id == org_id,
                paid_subq > Invoice.total_sek,
            )
            .order_by(Invoice.created_at.desc())
        )).all()

        return [
            {
                "id": str(inv.id),
                "invoice_number": inv.invoice_number,
                "customer_id": str(inv.customer_id) if inv.customer_id else None,
                "total_amount": float(inv.total_sek or 0),
                "amount_paid": float(paid or 0),
                "overpaid_by": float((paid or 0) - (inv.total_sek or 0)),
                "currency": inv.currency,
            }
            for inv, paid in rows
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
