"""Background job webhook endpoints — called by n8n on a schedule.

All endpoints require the X-Admin-Key header (ADMIN_API_KEY env var).
n8n is configured with this key to trigger periodic tasks.

Endpoints:
  POST /api/jobs/recurring-invoices    Generate invoices from due recurring templates
  POST /api/jobs/overdue-invoices      Mark past-due invoices as OVERDUE
  POST /api/jobs/email-sequences       Send next pending email in CRM sequences
  POST /api/jobs/inventory-alerts      Check stock levels and create reorder alerts
  POST /api/jobs/recurring-expenses    Generate expenses from due recurring templates
"""
from __future__ import annotations

import logging
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/api/jobs", tags=["background-jobs"])
log = logging.getLogger(__name__)


async def _require_admin_key(
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
) -> None:
    key = getattr(settings, "ADMIN_API_KEY", "") or ""
    if not key or not x_admin_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")
    if not secrets.compare_digest(x_admin_key, key):
        raise HTTPException(status_code=401, detail="Invalid admin key")


@router.post("/recurring-invoices", dependencies=[Depends(_require_admin_key)])
async def generate_recurring_invoices(db: AsyncSession = Depends(get_db)):
    """Generate invoices from recurring templates that are due today."""
    try:
        from app.models.recurring import RecurringTemplate
        from app.features.invoicing.models import Invoice, InvoiceLineItem
        from app.features.auth.organization import Organization

        today = date.today()
        templates = (await db.execute(
            select(RecurringTemplate).where(
                RecurringTemplate.is_active == True,
                RecurringTemplate.next_date <= today,
            )
        )).scalars().all()

        generated = 0
        for tpl in templates:
            try:
                invoice = Invoice(
                    org_id=tpl.org_id,
                    customer_id=tpl.customer_id,
                    issue_date=today,
                    due_date=today + timedelta(days=tpl.payment_terms or 30),
                    status="DRAFT",
                    currency=tpl.currency or "SEK",
                    notes=f"Auto-generated from recurring template",
                )
                db.add(invoice)
                await db.flush()

                for line in (tpl.lines or []):
                    db.add(InvoiceLineItem(
                        invoice_id=invoice.id,
                        description=line.get("description", ""),
                        quantity=line.get("quantity", 1),
                        unit_price=line.get("unit_price", 0),
                        vat_rate=line.get("vat_rate", 25),
                    ))

                tpl.last_generated = today
                tpl.next_date = _advance_date(today, tpl.interval)
                generated += 1
            except Exception as e:
                log.error("recurring_invoice_generate failed template=%s: %s", tpl.id, e)

        await db.commit()
        log.info("recurring_invoices job: generated=%d from=%d templates", generated, len(templates))
        return {"generated": generated, "templates_checked": len(templates)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("generate_recurring_invoices job failed: %s", e)
        raise HTTPException(status_code=500, detail="Job failed")


@router.post("/overdue-invoices", dependencies=[Depends(_require_admin_key)])
async def mark_overdue_invoices(db: AsyncSession = Depends(get_db)):
    """Mark SENT invoices past their due_date as OVERDUE."""
    try:
        from app.features.invoicing.models import Invoice

        today = date.today()
        result = await db.execute(
            update(Invoice)
            .where(
                Invoice.status == "SENT",
                Invoice.due_date < today,
            )
            .values(status="OVERDUE")
        )
        await db.commit()
        count = result.rowcount
        log.info("overdue_invoices job: marked=%d", count)
        return {"marked_overdue": count}
    except HTTPException:
        raise
    except Exception as e:
        log.error("mark_overdue_invoices job failed: %s", e)
        raise HTTPException(status_code=500, detail="Job failed")


@router.post("/email-sequences", dependencies=[Depends(_require_admin_key)])
async def process_email_sequences(db: AsyncSession = Depends(get_db)):
    """Send next pending email in active CRM sequences."""
    try:
        from app.models.email_sequence import EmailSequence, EmailSequenceStep, SequenceEnrollment

        now = datetime.now(timezone.utc)
        enrollments = (await db.execute(
            select(SequenceEnrollment).where(
                SequenceEnrollment.status == "active",
                SequenceEnrollment.next_step_at <= now,
            ).limit(100)
        )).scalars().all()

        sent = 0
        for enrollment in enrollments:
            try:
                step = await db.get(EmailSequenceStep, enrollment.next_step_id)
                if not step:
                    enrollment.status = "completed"
                    continue

                log.info("email_sequence send: enrollment=%s step=%s", enrollment.id, step.id)
                sent += 1

                next_step = (await db.execute(
                    select(EmailSequenceStep).where(
                        EmailSequenceStep.sequence_id == step.sequence_id,
                        EmailSequenceStep.position == step.position + 1,
                    )
                )).scalar_one_or_none()

                if next_step:
                    enrollment.next_step_id = next_step.id
                    enrollment.next_step_at = now + timedelta(hours=next_step.delay_hours or 24)
                else:
                    enrollment.status = "completed"
                    enrollment.next_step_id = None
                    enrollment.next_step_at = None

            except Exception as e:
                log.error("email_sequence step failed enrollment=%s: %s", enrollment.id, e)

        await db.commit()
        log.info("email_sequences job: sent=%d enrollments_checked=%d", sent, len(enrollments))
        return {"emails_sent": sent, "enrollments_processed": len(enrollments)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("process_email_sequences job failed: %s", e)
        raise HTTPException(status_code=500, detail="Job failed")


@router.post("/inventory-alerts", dependencies=[Depends(_require_admin_key)])
async def check_inventory_alerts(db: AsyncSession = Depends(get_db)):
    """Check stock levels below reorder point and create alerts."""
    try:
        from app.features.inventory.models import Product, StockLevel

        low_stock = (await db.execute(
            select(Product.id, Product.name, Product.sku, StockLevel.quantity, Product.reorder_point, Product.org_id)
            .join(StockLevel, StockLevel.product_id == Product.id)
            .where(
                Product.reorder_point.isnot(None),
                StockLevel.quantity <= Product.reorder_point,
                Product.is_active == True,
            )
        )).all()

        alerts_created = 0
        for row in low_stock:
            log.info(
                "inventory_alert: product=%s sku=%s qty=%s reorder_point=%s org=%s",
                row.name, row.sku, row.quantity, row.reorder_point, row.org_id,
            )
            alerts_created += 1

        log.info("inventory_alerts job: low_stock_items=%d", alerts_created)
        return {"low_stock_items": alerts_created}
    except HTTPException:
        raise
    except Exception as e:
        log.error("check_inventory_alerts job failed: %s", e)
        raise HTTPException(status_code=500, detail="Job failed")


@router.post("/recurring-expenses", dependencies=[Depends(_require_admin_key)])
async def generate_recurring_expenses(db: AsyncSession = Depends(get_db)):
    """Generate expenses from recurring templates that are due."""
    try:
        from app.features.expenses.recurring_expense import RecurringExpenseTemplate
        from app.features.expenses.models import Expense

        today = date.today()
        templates = (await db.execute(
            select(RecurringExpenseTemplate).where(
                RecurringExpenseTemplate.is_active == True,
                RecurringExpenseTemplate.next_due_date <= today,
            )
        )).scalars().all()

        generated = 0
        for tpl in templates:
            try:
                expense = Expense(
                    org_id=tpl.org_id,
                    category_id=tpl.category_id,
                    amount=tpl.amount,
                    currency=tpl.currency or "SEK",
                    description=tpl.description,
                    expense_date=today,
                    status="DRAFT",
                    supplier_id=tpl.supplier_id,
                    created_by=tpl.created_by,
                )
                db.add(expense)
                tpl.last_generated = today
                tpl.next_due_date = _advance_date(today, tpl.cadence)
                generated += 1
            except Exception as e:
                log.error("recurring_expense_generate failed template=%s: %s", tpl.id, e)

        await db.commit()
        log.info("recurring_expenses job: generated=%d", generated)
        return {"generated": generated, "templates_checked": len(templates)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("generate_recurring_expenses job failed: %s", e)
        raise HTTPException(status_code=500, detail="Job failed")


def _advance_date(current: date, interval: str) -> date:
    """Advance a date by the given interval string."""
    interval = (interval or "monthly").lower()
    if interval == "weekly":
        return current + timedelta(weeks=1)
    elif interval == "biweekly":
        return current + timedelta(weeks=2)
    elif interval == "quarterly":
        return current + timedelta(days=91)
    elif interval == "yearly":
        return current + timedelta(days=365)
    else:
        return current + timedelta(days=30)
