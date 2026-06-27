"""Customer statements router (Item 72).

Endpoints under ``/api/customer-statements``:

    GET  /{customer_id}?period_start=YYYY-MM-DD&period_end=YYYY-MM-DD
    GET  /{customer_id}/month?year=YYYY&month=MM

Both return a :class:`StatementOut`. The ``/month`` helper computes
month bounds server-side so mobile clients don't have to know that
"end of February" depends on leap years.

Statements are pure reads; a single audit event
(``customer_statement.viewed``) is emitted per call so sensitive
balance snapshots have the same traceability as invoice PDFs.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.credit_note import CreditNote, CreditNoteStatus
from app.models.invoicing import Customer, Invoice, Payment
from app.services import customer_statement as svc_72
from app.services.audit import log_action

router = APIRouter(
    prefix="/api/customer-statements",
    tags=["customer-statements"],
)

log = logging.getLogger(__name__)


class StatementInvoiceOut(BaseModel):
    id:         uuid.UUID
    number:     str | None
    issue_date: date
    due_date:   date
    total:      Decimal
    paid:       Decimal
    credited:   Decimal
    remaining:  Decimal
    status:     str


class StatementPaymentOut(BaseModel):
    id:           uuid.UUID
    invoice_id:   uuid.UUID | None
    payment_date: date
    amount:       Decimal
    method:       str | None


class StatementCreditOut(BaseModel):
    id:         uuid.UUID
    number:     str | None
    invoice_id: uuid.UUID | None
    issue_date: date
    total:      Decimal


class StatementEntryOut(BaseModel):
    entry_date: date
    kind:       str
    ref_id:     uuid.UUID
    amount:     Decimal
    balance:    Decimal
    label:      str


class StatementTotalsOut(BaseModel):
    invoices_issued: Decimal
    payments:        Decimal
    credits_issued:  Decimal
    outstanding:     Decimal


class StatementOut(BaseModel):
    customer_id:     uuid.UUID
    customer_name:   str
    period_start:    date
    period_end:      date
    opening_balance: Decimal
    closing_balance: Decimal
    invoices:        list[StatementInvoiceOut]
    payments:        list[StatementPaymentOut]
    credits:         list[StatementCreditOut]
    entries:         list[StatementEntryOut]
    totals:          StatementTotalsOut


# ── helpers ──────────────────────────────────────────────────────────────


async def _load_customer(
    db: AsyncSession, *, customer_id: uuid.UUID, org_id: uuid.UUID,
) -> Customer:
    row = await db.scalar(
        select(Customer).where(
            Customer.id == customer_id, Customer.org_id == org_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return row


async def _build(
    db: AsyncSession,
    *,
    customer_id:  uuid.UUID,
    org_id:       uuid.UUID,
    period_start: date,
    period_end:   date,
) -> svc_72.Statement:
    try:
        svc_72.validate_period(start=period_start, end=period_end)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    inv_rows = (await db.scalars(
        select(Invoice).where(
            Invoice.org_id == org_id,
            Invoice.customer_id == customer_id,
            Invoice.issue_date <= period_end,
        )
    )).all()

    invoice_ids = [i.id for i in inv_rows]

    # Payments attached to any of this customer's invoices in scope.
    pay_rows = []
    if invoice_ids:
        pay_rows = (await db.scalars(
            select(Payment).where(
                Payment.org_id == org_id,
                Payment.invoice_id.in_(invoice_ids),
                Payment.payment_date <= period_end,
            )
        )).all()

    cr_rows = (await db.scalars(
        select(CreditNote).where(
            CreditNote.org_id == org_id,
            CreditNote.customer_id == customer_id,
            CreditNote.issue_date <= period_end,
        )
    )).all()

    inv_src = [
        svc_72.InvoiceRow(
            id=str(i.id),
            number=i.invoice_number,
            issue_date=i.issue_date,
            due_date=i.due_date,
            total=Decimal(i.total_sek or 0),
            status=i.status.value if hasattr(i.status, "value") else str(i.status),
        )
        for i in inv_rows
    ]
    pay_src = [
        svc_72.PaymentRow(
            id=str(p.id),
            invoice_id=str(p.invoice_id) if p.invoice_id else None,
            payment_date=p.payment_date,
            amount=Decimal(p.amount or 0),
            method=(
                p.method.value if hasattr(p.method, "value") else str(p.method)
                if p.method is not None else None
            ),
        )
        for p in pay_rows
    ]
    cr_src = [
        svc_72.CreditRow(
            id=str(c.id),
            number=c.number,
            invoice_id=str(c.invoice_id) if c.invoice_id else None,
            issue_date=c.issue_date,
            total=Decimal(c.total or 0),
            status=(
                c.status.value if hasattr(c.status, "value") else str(c.status)
            ),
        )
        for c in cr_rows
    ]

    return svc_72.build_statement(
        customer_id=str(customer_id),
        period_start=period_start,
        period_end=period_end,
        invoices=inv_src,
        payments=pay_src,
        credits=cr_src,
    )


def _to_out(stmt: svc_72.Statement, *, customer: Customer) -> StatementOut:
    return StatementOut(
        customer_id=customer.id,
        customer_name=customer.company_name,
        period_start=stmt.period_start,
        period_end=stmt.period_end,
        opening_balance=stmt.opening_balance,
        closing_balance=stmt.closing_balance,
        invoices=[
            StatementInvoiceOut(
                id=uuid.UUID(i.id),
                number=i.number,
                issue_date=i.issue_date,
                due_date=i.due_date,
                total=i.total,
                paid=i.paid,
                credited=i.credited,
                remaining=i.remaining,
                status=i.status,
            )
            for i in stmt.invoices
        ],
        payments=[
            StatementPaymentOut(
                id=uuid.UUID(p.id),
                invoice_id=uuid.UUID(p.invoice_id) if p.invoice_id else None,
                payment_date=p.payment_date,
                amount=p.amount,
                method=p.method,
            )
            for p in stmt.payments
        ],
        credits=[
            StatementCreditOut(
                id=uuid.UUID(c.id),
                number=c.number,
                invoice_id=uuid.UUID(c.invoice_id) if c.invoice_id else None,
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
            invoices_issued=stmt.totals.invoices_issued,
            payments=stmt.totals.payments,
            credits_issued=stmt.totals.credits_issued,
            outstanding=stmt.totals.outstanding,
        ),
    )


# ── endpoints ────────────────────────────────────────────────────────────


@router.get("/{customer_id}", response_model=StatementOut)
async def get_statement(
    customer_id:  uuid.UUID,
    request:      Request,
    period_start: date = Query(...),
    period_end:   date = Query(...),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    customer = await _load_customer(
        db, customer_id=customer_id, org_id=member.org_id,
    )
    stmt = await _build(
        db,
        customer_id=customer_id,
        org_id=member.org_id,
        period_start=period_start,
        period_end=period_end,
    )
    await log_action(
        db,
        action="customer_statement.viewed",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="customer",
        target_id=str(customer_id),
        request=request,
        extra={
            "period_start":    period_start.isoformat(),
            "period_end":      period_end.isoformat(),
            "opening_balance": str(stmt.opening_balance),
            "closing_balance": str(stmt.closing_balance),
        },
    )
    await db.commit()
    return _to_out(stmt, customer=customer)


@router.get("/{customer_id}/month", response_model=StatementOut)
async def get_monthly_statement(
    customer_id: uuid.UUID,
    request:     Request,
    year:        int = Query(..., ge=2000, le=3000),
    month:       int = Query(..., ge=1, le=12),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    try:
        start, end = svc_72.month_bounds(year=year, month=month)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    user, member = ctx
    customer = await _load_customer(
        db, customer_id=customer_id, org_id=member.org_id,
    )
    stmt = await _build(
        db,
        customer_id=customer_id,
        org_id=member.org_id,
        period_start=start,
        period_end=end,
    )
    await log_action(
        db,
        action="customer_statement.viewed",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="customer",
        target_id=str(customer_id),
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
    return _to_out(stmt, customer=customer)
