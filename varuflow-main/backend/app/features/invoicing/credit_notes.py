"""Customer credit-notes router (Item 70).

Endpoints under ``/api/credit-notes``:

    GET    ""                       list (optional customer_id, status)
    POST   ""                       create DRAFT with lines
    GET    /{credit_note_id}         detail (incl. lines)
    PATCH  /{credit_note_id}         edit DRAFT only (lines + meta)
    DELETE /{credit_note_id}         delete DRAFT only
    POST   /{credit_note_id}/issue   DRAFT → ISSUED (mints CN number)
    POST   /{credit_note_id}/void    * → VOIDED with reason

Business invariants:
* ISSUED and VOIDED documents are immutable — the only way to
  "edit" one is to void it and create a new draft.
* A credit note bound to an invoice may not exceed the invoice's
  outstanding balance when issued. Standalone credits (no invoice)
  have no cap.
* Number minting is tenant-scoped; the transaction takes
  ``SELECT … FOR UPDATE`` on the org row to serialise issuance and
  avoid duplicate ``CN-YYYY-NNNN`` numbers under concurrent load —
  same pattern as ``invoicing.create_invoice``.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.features.invoicing.credit_note import (
    CreditNote, CreditNoteLine, CreditNoteStatus,
)
from app.features.invoicing.models import Customer, Invoice, InvoiceStatus, Payment
from app.features.auth.organization import Organization
from app.services import credit_note as svc_70
from app.services.audit import log_action
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/credit-notes", tags=["credit-notes"], dependencies=[Depends(require_module("invoicing"))])

log = logging.getLogger(__name__)


class CreditNoteLineIn(BaseModel):
    description: str
    quantity:    Decimal
    unit_price:  Decimal
    tax_rate:    Decimal = Decimal("25.00")


class CreditNoteCreate(BaseModel):
    customer_id: uuid.UUID
    invoice_id:  uuid.UUID | None = None
    issue_date:  date
    currency:    str = "SEK"
    reason:      str | None = None
    lines:       list[CreditNoteLineIn]


class CreditNoteUpdate(BaseModel):
    invoice_id:  uuid.UUID | None = None
    issue_date:  date | None = None
    currency:    str | None = None
    reason:      str | None = None
    lines:       list[CreditNoteLineIn] | None = None


class VoidBody(BaseModel):
    reason: str


class CreditNoteLineOut(BaseModel):
    id:          uuid.UUID
    description: str
    quantity:    Decimal
    unit_price:  Decimal
    tax_rate:    Decimal
    line_total:  Decimal
    position:    int


class CreditNoteOut(BaseModel):
    id:          uuid.UUID
    customer_id: uuid.UUID
    invoice_id:  uuid.UUID | None
    number:      str | None
    status:      CreditNoteStatus
    issue_date:  date
    reason:      str | None
    currency:    str
    subtotal:    Decimal
    tax_total:   Decimal
    total:       Decimal
    issued_at:   datetime | None
    voided_at:   datetime | None
    void_reason: str | None
    created_at:  datetime
    updated_at:  datetime
    lines:       list[CreditNoteLineOut]


# ── Helpers ───────────────────────────────────────────────────────────────


async def _load(
    db: AsyncSession, *, credit_note_id: uuid.UUID, org_id: uuid.UUID,
) -> CreditNote:
    row = await db.get(CreditNote, credit_note_id)
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Credit note not found")
    return row


async def _assert_customer_belongs(
    db: AsyncSession, *, customer_id: uuid.UUID, org_id: uuid.UUID,
) -> Customer:
    cust = await db.scalar(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.org_id == org_id,
        )
    )
    if cust is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return cust


async def _assert_invoice_belongs(
    db: AsyncSession, *, invoice_id: uuid.UUID, org_id: uuid.UUID,
    expected_customer_id: uuid.UUID,
) -> Invoice:
    inv = await db.scalar(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.org_id == org_id,
        )
    )
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.customer_id != expected_customer_id:
        raise HTTPException(
            status_code=400,
            detail="invoice and credit-note customer_id do not match",
        )
    return inv


def _validate_lines(body_lines: list[CreditNoteLineIn]) -> list[dict]:
    if not body_lines:
        raise HTTPException(status_code=400, detail="lines must not be empty")
    out: list[dict] = []
    for ln in body_lines:
        try:
            desc  = svc_70.validate_description(ln.description)
            qty   = svc_70.validate_quantity(ln.quantity)
            price = svc_70.validate_unit_price(ln.unit_price)
            tax   = svc_70.validate_tax_rate(ln.tax_rate)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        out.append({
            "description": desc,
            "quantity":    qty,
            "unit_price":  price,
            "tax_rate":    tax,
        })
    return out


def _to_out(row: CreditNote) -> CreditNoteOut:
    return CreditNoteOut(
        id=row.id,
        customer_id=row.customer_id,
        invoice_id=row.invoice_id,
        number=row.number,
        status=row.status,
        issue_date=row.issue_date,
        reason=row.reason,
        currency=row.currency,
        subtotal=row.subtotal,
        tax_total=row.tax_total,
        total=row.total,
        issued_at=row.issued_at,
        voided_at=row.voided_at,
        void_reason=row.void_reason,
        created_at=row.created_at,
        updated_at=row.updated_at,
        lines=[
            CreditNoteLineOut(
                id=l.id,
                description=l.description,
                quantity=l.quantity,
                unit_price=l.unit_price,
                tax_rate=l.tax_rate,
                line_total=l.line_total,
                position=l.position,
            )
            for l in sorted(row.lines, key=lambda x: x.position)
        ],
    )


def _replace_lines(
    row: CreditNote, new_lines: list[dict],
) -> None:
    row.lines.clear()
    totals = svc_70.compute_totals(new_lines)
    for idx, ln in enumerate(new_lines):
        part = svc_70.compute_line(
            quantity=ln["quantity"],
            unit_price=ln["unit_price"],
            tax_rate=ln["tax_rate"],
        )
        row.lines.append(CreditNoteLine(
            description=ln["description"],
            quantity=ln["quantity"],
            unit_price=ln["unit_price"],
            tax_rate=ln["tax_rate"],
            line_total=part.line_total,
            position=idx,
        ))
    row.subtotal  = totals.subtotal
    row.tax_total = totals.tax_total
    row.total     = totals.total


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.get("", response_model=list[CreditNoteOut])
async def list_credit_notes(
    customer_id: uuid.UUID | None = Query(default=None),
    status_:     str | None = Query(default=None, alias="status"),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _user, member = ctx
    stmt = select(CreditNote).where(CreditNote.org_id == member.org_id)
    if customer_id is not None:
        stmt = stmt.where(CreditNote.customer_id == customer_id)
    if status_ is not None:
        try:
            st = CreditNoteStatus(status_)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid status")
        stmt = stmt.where(CreditNote.status == st)
    stmt = stmt.order_by(CreditNote.created_at.desc())
    rows = (await db.scalars(stmt)).all()
    return [_to_out(r) for r in rows]


@router.post(
    "", response_model=CreditNoteOut, status_code=status.HTTP_201_CREATED,
)
async def create_credit_note(
    body:    CreditNoteCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    await _assert_customer_belongs(
        db, customer_id=body.customer_id, org_id=member.org_id,
    )
    if body.invoice_id is not None:
        await _assert_invoice_belongs(
            db,
            invoice_id=body.invoice_id,
            org_id=member.org_id,
            expected_customer_id=body.customer_id,
        )
    try:
        currency = svc_70.validate_currency(body.currency)
        reason   = svc_70.validate_reason(body.reason)
        issue    = svc_70.validate_issue_date(body.issue_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    lines = _validate_lines(body.lines)
    totals = svc_70.compute_totals(lines)

    row = CreditNote(
        org_id=member.org_id,
        customer_id=body.customer_id,
        invoice_id=body.invoice_id,
        status=CreditNoteStatus.DRAFT,
        issue_date=issue,
        reason=reason,
        currency=currency,
        subtotal=totals.subtotal,
        tax_total=totals.tax_total,
        total=totals.total,
    )
    for idx, ln in enumerate(lines):
        part = svc_70.compute_line(
            quantity=ln["quantity"],
            unit_price=ln["unit_price"],
            tax_rate=ln["tax_rate"],
        )
        row.lines.append(CreditNoteLine(
            description=ln["description"],
            quantity=ln["quantity"],
            unit_price=ln["unit_price"],
            tax_rate=ln["tax_rate"],
            line_total=part.line_total,
            position=idx,
        ))
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="creditnote.created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="credit_note",
        target_id=str(row.id),
        request=request,
        extra={
            "customer_id": str(body.customer_id),
            "invoice_id":  str(body.invoice_id) if body.invoice_id else None,
            "total":       str(totals.total),
        },
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.get("/{credit_note_id}", response_model=CreditNoteOut)
async def get_credit_note(
    credit_note_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _user, member = ctx
    row = await _load(
        db, credit_note_id=credit_note_id, org_id=member.org_id,
    )
    return _to_out(row)


@router.patch("/{credit_note_id}", response_model=CreditNoteOut)
async def update_credit_note(
    credit_note_id: uuid.UUID,
    body:    CreditNoteUpdate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(
        db, credit_note_id=credit_note_id, org_id=member.org_id,
    )
    if row.status is not CreditNoteStatus.DRAFT:
        raise HTTPException(
            status_code=409,
            detail="only DRAFT credit notes may be edited",
        )

    changes: dict = {}
    try:
        if body.currency is not None:
            row.currency = svc_70.validate_currency(body.currency)
            changes["currency"] = row.currency
        if body.reason is not None:
            row.reason = svc_70.validate_reason(body.reason)
            changes["reason"] = "set"
        if body.issue_date is not None:
            row.issue_date = svc_70.validate_issue_date(body.issue_date)
            changes["issue_date"] = row.issue_date.isoformat()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if body.invoice_id is not None:
        await _assert_invoice_belongs(
            db,
            invoice_id=body.invoice_id,
            org_id=member.org_id,
            expected_customer_id=row.customer_id,
        )
        row.invoice_id = body.invoice_id
        changes["invoice_id"] = str(body.invoice_id)

    if body.lines is not None:
        lines = _validate_lines(body.lines)
        _replace_lines(row, lines)
        changes["lines"] = len(lines)

    await db.flush()
    await log_action(
        db,
        action="creditnote.updated",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="credit_note",
        target_id=str(row.id),
        request=request,
        extra=changes,
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.delete("/{credit_note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credit_note(
    credit_note_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(
        db, credit_note_id=credit_note_id, org_id=member.org_id,
    )
    if row.status is not CreditNoteStatus.DRAFT:
        raise HTTPException(
            status_code=409,
            detail="only DRAFT credit notes may be deleted",
        )
    await db.delete(row)
    await log_action(
        db,
        action="creditnote.deleted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="credit_note",
        target_id=str(credit_note_id),
        request=request,
    )
    await db.commit()


async def _existing_credit_for_invoice(
    db: AsyncSession, *, invoice_id: uuid.UUID, org_id: uuid.UUID,
    exclude_id: uuid.UUID,
) -> Decimal:
    # Sum of *non-voided* credits already attached to the invoice.
    res = await db.execute(
        select(func.coalesce(func.sum(CreditNote.total), 0)).where(
            CreditNote.org_id == org_id,
            CreditNote.invoice_id == invoice_id,
            CreditNote.status == CreditNoteStatus.ISSUED,
            CreditNote.id != exclude_id,
        )
    )
    return Decimal(res.scalar() or 0)


async def _paid_on_invoice(
    db: AsyncSession, *, invoice_id: uuid.UUID,
) -> Decimal:
    res = await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.invoice_id == invoice_id,
        )
    )
    return Decimal(res.scalar() or 0)


@router.post("/{credit_note_id}/issue", response_model=CreditNoteOut)
async def issue_credit_note(
    credit_note_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx

    # Lock the tenant so concurrent /issue calls cannot mint the same
    # CN-YYYY-NNNN sequence.
    await db.execute(
        select(Organization.id)
        .where(Organization.id == member.org_id)
        .with_for_update()
    )

    row = await _load(
        db, credit_note_id=credit_note_id, org_id=member.org_id,
    )
    try:
        svc_70.assert_transition(row.status, CreditNoteStatus.ISSUED)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    if not row.lines:
        raise HTTPException(
            status_code=400, detail="credit note has no lines",
        )

    if row.invoice_id is not None:
        inv = await db.get(Invoice, row.invoice_id)
        if inv is None or inv.org_id != member.org_id:
            raise HTTPException(
                status_code=404, detail="source invoice missing",
            )
        paid  = await _paid_on_invoice(db, invoice_id=row.invoice_id)
        other = await _existing_credit_for_invoice(
            db, invoice_id=row.invoice_id,
            org_id=member.org_id,
            exclude_id=row.id,
        )
        try:
            svc_70.assert_fits_invoice(
                credit_total=row.total,
                invoice_total=inv.total_sek,
                invoice_paid=paid,
                invoice_credited=other,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Mint number.
    year = row.issue_date.year
    used_rows = await db.execute(
        select(CreditNote.number).where(
            CreditNote.org_id == member.org_id,
            CreditNote.number.isnot(None),
        )
    )
    used = {n for (n,) in used_rows.all()}
    number = svc_70.next_number(year=year, existing=used)

    row.number = number
    row.status = CreditNoteStatus.ISSUED
    row.issued_at = datetime.now(tz=timezone.utc)

    await db.flush()
    await log_action(
        db,
        action="creditnote.issued",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="credit_note",
        target_id=str(row.id),
        request=request,
        extra={"number": number, "total": str(row.total)},
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.post("/{credit_note_id}/void", response_model=CreditNoteOut)
async def void_credit_note(
    credit_note_id: uuid.UUID,
    body:    VoidBody,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(
        db, credit_note_id=credit_note_id, org_id=member.org_id,
    )
    try:
        svc_70.assert_transition(row.status, CreditNoteStatus.VOIDED)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    reason = (body.reason or "").strip()
    if not reason:
        raise HTTPException(
            status_code=400, detail="void reason is required",
        )
    if len(reason) > svc_70.MAX_REASON_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"reason too long ({svc_70.MAX_REASON_LENGTH} max)",
        )

    prev_status = row.status
    row.status = CreditNoteStatus.VOIDED
    row.voided_at = datetime.now(tz=timezone.utc)
    row.void_reason = reason

    await db.flush()
    await log_action(
        db,
        action="creditnote.voided",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="credit_note",
        target_id=str(row.id),
        request=request,
        extra={"from": prev_status.value, "reason": reason},
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)
