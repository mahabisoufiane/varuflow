"""Zakat Estimation for Saudi Entities

Zakat = 2.5% of zakatable assets held for ≥ 1 Hijri year (≈ 354 days).
Zakatable assets = inventory value + long-outstanding receivables − payables.

READ-ONLY — no database writes.

Endpoint:
  GET /api/mena/zakat/estimate?as_of_date=YYYY-MM-DD
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.features.inventory.models import Product, StockLevel
from app.features.invoicing.models import Invoice, InvoiceStatus
from app.features.purchases.payable_invoice import PayableInvoice

router = APIRouter(prefix="/api/mena/zakat", tags=["mena_zakat"], dependencies=[Depends(require_module("finance"))])
log = logging.getLogger(__name__)

# Nisab threshold: 595g × ~250 SAR/g (indicative — gold price varies daily)
NISAB_SAR = Decimal("148750.00")
ZAKAT_RATE = Decimal("0.025")
# Hijri year in Gregorian days
HIJRI_YEAR_DAYS = 354


class ZakatEstimateOut(BaseModel):
    as_of_date: str
    inventory_value: str
    receivables: str
    payables: str
    zakatable_base: str
    nisab_threshold_sar: str
    above_nisab: bool
    zakat_due: str
    currency: str
    note: str


@router.get("/estimate", response_model=ZakatEstimateOut)
async def estimate_zakat(
    as_of_date: Optional[str] = Query(None, description="YYYY-MM-DD; defaults to today"),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Estimate Zakat liability as of a given date.

    DISCLAIMER: This is a simplified estimate for planning purposes only.
    Actual Zakat obligation depends on the full financial position of the
    entity and must be determined by a qualified Islamic scholar and auditor.
    """
    _, member = ctx
    org_id: uuid.UUID = member.org_id

    try:
        if as_of_date:
            calc_date = date.fromisoformat(as_of_date)
        else:
            calc_date = date.today()

        hijri_cutoff = calc_date - timedelta(days=HIJRI_YEAR_DAYS)

        # 1. Inventory value: sum(stock_level.quantity × product.price)
        inv_rows = await db.execute(
            select(
                func.coalesce(
                    func.sum(StockLevel.quantity * Product.sell_price), 0
                ).label("total")
            )
            .join(Product, StockLevel.product_id == Product.id)
            .where(
                StockLevel.org_id == org_id,
                Product.org_id == org_id,
                Product.is_active == True,  # noqa: E712
            )
        )
        inventory_value = Decimal(str(inv_rows.scalar_one() or 0))

        # 2. Long-outstanding receivables: SENT/OVERDUE invoices older than one Hijri year
        rec_rows = await db.execute(
            select(func.coalesce(func.sum(Invoice.total_sek), 0).label("total"))
            .where(
                Invoice.org_id == org_id,
                Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE]),
                Invoice.issue_date <= hijri_cutoff,
            )
        )
        receivables = Decimal(str(rec_rows.scalar_one() or 0))

        # 3. Payables: APPROVED payable invoices due before as_of_date
        pay_rows = await db.execute(
            select(func.coalesce(func.sum(PayableInvoice.total), 0).label("total"))
            .where(
                PayableInvoice.org_id == org_id,
                PayableInvoice.status == "APPROVED",
                PayableInvoice.due_date <= calc_date,
            )
        )
        payables = Decimal(str(pay_rows.scalar_one() or 0))

        zakatable_base = max(Decimal("0"), inventory_value + receivables - payables)
        above_nisab = zakatable_base >= NISAB_SAR
        zakat_due = (zakatable_base * ZAKAT_RATE).quantize(Decimal("0.01")) if above_nisab else Decimal("0.00")

        return ZakatEstimateOut(
            as_of_date=calc_date.isoformat(),
            inventory_value=str(inventory_value.quantize(Decimal("0.01"))),
            receivables=str(receivables.quantize(Decimal("0.01"))),
            payables=str(payables.quantize(Decimal("0.01"))),
            zakatable_base=str(zakatable_base.quantize(Decimal("0.01"))),
            nisab_threshold_sar=str(NISAB_SAR),
            above_nisab=above_nisab,
            zakat_due=str(zakat_due),
            currency="SAR",
            note=(
                "Estimate only — based on inventory book value, long-outstanding receivables "
                "(>354 days), and approved payables as of the selected date. "
                "Consult a qualified Islamic scholar and auditor for your actual Zakat obligation."
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error("zakat_estimate failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
