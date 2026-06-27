"""Supplier statements router (Item 93).

Endpoints under ``/api/supplier-statements``:

    GET  /{supplier_id}?period_start=YYYY-MM-DD&period_end=YYYY-MM-DD
    GET  /{supplier_id}/month?year=YYYY&month=MM

Both return a :class:`StatementOut`. Mirror of customer statements
(Item 72) flipped to the accounts-payable side. Pure read — one
audit entry (``supplier_statement.viewed``) per call.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.features.inventory.models import Supplier
from app.features.purchases.payable_invoice import PayableInvoice
from .supplier_credit_note import (
    SupplierCreditNote, SupplierCreditNoteStatus,
)
from app.services import supplier_statement as svc_93
from app.services.audit import log_action

router = APIRouter(
    prefix="/api/supplier-statements",
    tags=["supplier-statements"],
    dependencies=[Depends(require_module("finance"))],
)

log = logging.getLogger(__name__)


class StatementPayableOut(BaseModel):
    id:         uuid.UUID
    number:     str | None
    issue_date: date
    due_date:   date | None
    total:      Decimal
    credited:   Decimal
    remaining:  Decimal
    status:     str


class StatementCreditOut(BaseModel):
    id:                uuid.UUID
    number:            str | None
    purchase_order_id: uuid.UUID | None
    issue_date:        date
    total:             Decimal


class StatementEntryOut(BaseModel):
    entry_date: date
    kind:       str
    ref_id:     uuid.UUID
    amount:     Decimal
    balance:    Decimal
    label:      str


class StatementTotalsOut(BaseModel):
    payables_issued: Decimal
    credits_issued:  Decimal
    outstanding:     Decimal


class StatementOut(BaseModel):
    supplier_id:     uuid.UUID
    supplier_name:   str
    period_start:    date
    period_end:      date
    opening_balance: Decimal
    closing_balance: Decimal
    payables:        list[StatementPayableOut]
    credits:         list[StatementCreditOut]
    entries:         list[StatementEntryOut]
    totals:          StatementTotalsOut


async def _load_supplier(
    db: AsyncSession, *, supplier_id: uuid.UUID, org_id: uuid.UUID,
) -> Supplier:
    row = await db.scalar(
        select(Supplier).where(
            Supplier.id == supplier_id, Supplier.org_id == org_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return row


async def _build(
    db: AsyncSession,
    *,
    supplier_id:  uuid.UUID,
    org_id:       uuid.UUID,
    period_start: date,
    period_end:   date,
) -> svc_93.Statement:
    try:
        svc_93.validate_period(start=period_start, end=period_end)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    pv_rows = (await db.scalars(
        select(PayableInvoice).where(
            PayableInvoice.org_id == org_id,
            PayableInvoice.supplier_id == supplier_id,
        )
    )).all()
    # Filter by issue_date ≤ period_end — payables with no issue_date
    # yet (auto-drafts awaiting the supplier's bill) are excluded from
    # the statement since they have no balance impact without a date.
    pv_rows = [p for p in pv_rows if p.issue_date is not None
               and p.issue_date <= period_end]

    cr_rows = (await db.scalars(
        select(SupplierCreditNote).where(
            SupplierCreditNote.org_id == org_id,
            SupplierCreditNote.supplier_id == supplier_id,
            SupplierCreditNote.issue_date <= period_end,
        )
    )).all()

    pv_src = [
        svc_93.PayableRow(
            id=str(p.id),
            number=p.invoice_number,
            issue_date=p.issue_date,
            due_date=p.due_date,
            total=Decimal(p.total or 0),
            status=str(p.status),
        )
        for p in pv_rows
    ]
    cr_src = [
        svc_93.CreditRow(
            id=str(c.id),
            number=c.number,
            purchase_order_id=(
                str(c.purchase_order_id) if c.purchase_order_id else None
            ),
            issue_date=c.issue_date,
            total=Decimal(c.total or 0),
            status=(
                c.status.value if hasattr(c.status, "value")
                else str(c.status)
            ),
        )
        for c in cr_rows
    ]

    return svc_93.build_statement(
        supplier_id=str(supplier_id),
        period_start=period_start,
        period_end=period_end,
        payables=pv_src,
        credits=cr_src,
    )


def _to_out(stmt: svc_93.Statement, *, supplier: Supplier) -> StatementOut:
    return StatementOut(
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        period_start=stmt.period_start,
        period_end=stmt.period_end,
        opening_balance=stmt.opening_balance,
        closing_balance=stmt.closing_balance,
        payables=[
            StatementPayableOut(
                id=uuid.UUID(p.id),
                number=p.number,
                issue_date=p.issue_date,
                due_date=p.due_date,
                total=p.total,
                credited=p.credited,
                remaining=p.remaining,
                status=p.status,
            )
            for p in stmt.payables
        ],
        credits=[
            StatementCreditOut(
                id=uuid.UUID(c.id),
                number=c.number,
                purchase_order_id=(
                    uuid.UUID(c.purchase_order_id)
                    if c.purchase_order_id else None
                ),
                issue_date=c.issue_date,
                total=c.total,
            )
            for c in stmt.credits
        ],
        entries=[
            StatementEntryOut(
                entry_date=e.entry_date,
                kind=e.kind,
                ref_id=uuid.UUID(e.ref_id),
                amount=e.amount,
                balance=e.balance,
                label=e.label,
            )
            for e in stmt.entries
        ],
        totals=StatementTotalsOut(
            payables_issued=stmt.totals.payables_issued,
            credits_issued=stmt.totals.credits_issued,
            outstanding=stmt.totals.outstanding,
        ),
    )


@router.get("/{supplier_id}", response_model=StatementOut)
async def get_statement(
    supplier_id:  uuid.UUID,
    request:      Request,
    period_start: date = Query(...),
    period_end:   date = Query(...),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    supplier = await _load_supplier(
        db, supplier_id=supplier_id, org_id=member.org_id,
    )
    stmt = await _build(
        db,
        supplier_id=supplier_id,
        org_id=member.org_id,
        period_start=period_start,
        period_end=period_end,
    )
    await log_action(
        db,
        action="supplier_statement.viewed",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="supplier",
        target_id=str(supplier_id),
        request=request,
        extra={
            "period_start":    period_start.isoformat(),
            "period_end":      period_end.isoformat(),
            "opening_balance": str(stmt.opening_balance),
            "closing_balance": str(stmt.closing_balance),
        },
    )
    await db.commit()
    return _to_out(stmt, supplier=supplier)


@router.get("/{supplier_id}/month", response_model=StatementOut)
async def get_monthly_statement(
    supplier_id: uuid.UUID,
    request:     Request,
    year:        int = Query(..., ge=2000, le=3000),
    month:       int = Query(..., ge=1, le=12),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    try:
        start, end = svc_93.month_bounds(year=year, month=month)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    user, member = ctx
    supplier = await _load_supplier(
        db, supplier_id=supplier_id, org_id=member.org_id,
    )
    stmt = await _build(
        db,
        supplier_id=supplier_id,
        org_id=member.org_id,
        period_start=start,
        period_end=end,
    )
    await log_action(
        db,
        action="supplier_statement.viewed",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="supplier",
        target_id=str(supplier_id),
        request=request,
        extra={
            "period_start":    start.isoformat(),
            "period_end":      end.isoformat(),
            "year":            year,
            "month":           month,
            "closing_balance": str(stmt.closing_balance),
        },
    )
    await db.commit()
    return _to_out(stmt, supplier=supplier)
