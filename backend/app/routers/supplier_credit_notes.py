"""Supplier credit-notes router (Item 92).

Endpoints under ``/api/supplier-credit-notes``:

    GET    ""                                list (optional supplier_id, status)
    POST   ""                                create DRAFT with lines
    GET    /{supplier_credit_note_id}        detail (incl. lines)
    PATCH  /{supplier_credit_note_id}        edit DRAFT only (lines + meta)
    DELETE /{supplier_credit_note_id}        delete DRAFT only
    POST   /{supplier_credit_note_id}/issue  DRAFT → ISSUED (mints SCN number)
    POST   /{supplier_credit_note_id}/void   * → VOIDED with reason

Business invariants:
* ISSUED and VOIDED documents are immutable — the only way to
  "edit" one is to void it and create a new draft.
* A credit note bound to a PO may not exceed the PO's outstanding
  un-credited balance when issued. Standalone credits (no PO) are
  uncapped.
* Number minting is tenant-scoped; the transaction takes
  ``SELECT … FOR UPDATE`` on the org row to serialise issuance and
  avoid duplicate ``SCN-YYYY-NNNN`` numbers under concurrent load.
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
from app.models.inventory import PurchaseOrder, Supplier
from app.models.organization import Organization
from app.models.supplier_credit_note import (
    SupplierCreditNote, SupplierCreditNoteLine, SupplierCreditNoteStatus,
)
from app.services import supplier_credit_note as svc_92
from app.services.audit import log_action

router = APIRouter(
    prefix="/api/supplier-credit-notes", tags=["supplier-credit-notes"],
)

log = logging.getLogger(__name__)


class SupplierCreditNoteLineIn(BaseModel):
    description: str
    quantity:    Decimal
    unit_price:  Decimal
    tax_rate:    Decimal = Decimal("25.00")


class SupplierCreditNoteCreate(BaseModel):
    supplier_id:       uuid.UUID
    purchase_order_id: uuid.UUID | None = None
    issue_date:        date
    currency:          str = "SEK"
    reason:            str | None = None
    lines:             list[SupplierCreditNoteLineIn]


class SupplierCreditNoteUpdate(BaseModel):
    purchase_order_id: uuid.UUID | None = None
    issue_date:        date | None = None
    currency:          str | None = None
    reason:            str | None = None
    lines:             list[SupplierCreditNoteLineIn] | None = None


class VoidBody(BaseModel):
    reason: str


class SupplierCreditNoteLineOut(BaseModel):
    id:          uuid.UUID
    description: str
    quantity:    Decimal
    unit_price:  Decimal
    tax_rate:    Decimal
    line_total:  Decimal
    position:    int


class SupplierCreditNoteOut(BaseModel):
    id:                uuid.UUID
    supplier_id:       uuid.UUID
    purchase_order_id: uuid.UUID | None
    number:            str | None
    status:            SupplierCreditNoteStatus
    issue_date:        date
    reason:            str | None
    currency:          str
    subtotal:          Decimal
    tax_total:         Decimal
    total:             Decimal
    issued_at:         datetime | None
    voided_at:         datetime | None
    void_reason:       str | None
    created_at:        datetime
    updated_at:        datetime
    lines:             list[SupplierCreditNoteLineOut]


async def _load(
    db: AsyncSession, *, scn_id: uuid.UUID, org_id: uuid.UUID,
) -> SupplierCreditNote:
    row = await db.get(SupplierCreditNote, scn_id)
    if row is None or row.org_id != org_id:
        raise HTTPException(
            status_code=404, detail="Supplier credit note not found",
        )
    return row


async def _assert_supplier_belongs(
    db: AsyncSession, *, supplier_id: uuid.UUID, org_id: uuid.UUID,
) -> Supplier:
    sup = await db.scalar(
        select(Supplier).where(
            Supplier.id == supplier_id,
            Supplier.org_id == org_id,
        )
    )
    if sup is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return sup


async def _assert_po_belongs(
    db: AsyncSession, *, purchase_order_id: uuid.UUID, org_id: uuid.UUID,
    expected_supplier_id: uuid.UUID,
) -> PurchaseOrder:
    po = await db.scalar(
        select(PurchaseOrder).where(
            PurchaseOrder.id == purchase_order_id,
            PurchaseOrder.org_id == org_id,
        )
    )
    if po is None:
        raise HTTPException(
            status_code=404, detail="Purchase order not found",
        )
    if po.supplier_id != expected_supplier_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "purchase order and supplier-credit-note "
                "supplier_id do not match"
            ),
        )
    return po


def _validate_lines(body_lines: list[SupplierCreditNoteLineIn]) -> list[dict]:
    if not body_lines:
        raise HTTPException(status_code=400, detail="lines must not be empty")
    out: list[dict] = []
    for ln in body_lines:
        try:
            desc  = svc_92.validate_description(ln.description)
            qty   = svc_92.validate_quantity(ln.quantity)
            price = svc_92.validate_unit_price(ln.unit_price)
            tax   = svc_92.validate_tax_rate(ln.tax_rate)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        out.append({
            "description": desc,
            "quantity":    qty,
            "unit_price":  price,
            "tax_rate":    tax,
        })
    return out


def _to_out(row: SupplierCreditNote) -> SupplierCreditNoteOut:
    return SupplierCreditNoteOut(
        id=row.id,
        supplier_id=row.supplier_id,
        purchase_order_id=row.purchase_order_id,
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
            SupplierCreditNoteLineOut(
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
    row: SupplierCreditNote, new_lines: list[dict],
) -> None:
    row.lines.clear()
    totals = svc_92.compute_totals(new_lines)
    for idx, ln in enumerate(new_lines):
        part = svc_92.compute_line(
            quantity=ln["quantity"],
            unit_price=ln["unit_price"],
            tax_rate=ln["tax_rate"],
        )
        row.lines.append(SupplierCreditNoteLine(
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


@router.get("", response_model=list[SupplierCreditNoteOut])
async def list_supplier_credit_notes(
    supplier_id: uuid.UUID | None = Query(default=None),
    status_:     str | None = Query(default=None, alias="status"),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _user, member = ctx
    stmt = select(SupplierCreditNote).where(
        SupplierCreditNote.org_id == member.org_id,
    )
    if supplier_id is not None:
        stmt = stmt.where(SupplierCreditNote.supplier_id == supplier_id)
    if status_ is not None:
        try:
            st = SupplierCreditNoteStatus(status_)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid status")
        stmt = stmt.where(SupplierCreditNote.status == st)
    stmt = stmt.order_by(SupplierCreditNote.created_at.desc())
    rows = (await db.scalars(stmt)).all()
    return [_to_out(r) for r in rows]


@router.post(
    "", response_model=SupplierCreditNoteOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_supplier_credit_note(
    body:    SupplierCreditNoteCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    await _assert_supplier_belongs(
        db, supplier_id=body.supplier_id, org_id=member.org_id,
    )
    if body.purchase_order_id is not None:
        await _assert_po_belongs(
            db,
            purchase_order_id=body.purchase_order_id,
            org_id=member.org_id,
            expected_supplier_id=body.supplier_id,
        )
    try:
        currency = svc_92.validate_currency(body.currency)
        reason   = svc_92.validate_reason(body.reason)
        issue    = svc_92.validate_issue_date(body.issue_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    lines = _validate_lines(body.lines)
    totals = svc_92.compute_totals(lines)

    row = SupplierCreditNote(
        org_id=member.org_id,
        supplier_id=body.supplier_id,
        purchase_order_id=body.purchase_order_id,
        status=SupplierCreditNoteStatus.DRAFT,
        issue_date=issue,
        reason=reason,
        currency=currency,
        subtotal=totals.subtotal,
        tax_total=totals.tax_total,
        total=totals.total,
    )
    for idx, ln in enumerate(lines):
        part = svc_92.compute_line(
            quantity=ln["quantity"],
            unit_price=ln["unit_price"],
            tax_rate=ln["tax_rate"],
        )
        row.lines.append(SupplierCreditNoteLine(
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
        action="supplier_credit_note.created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="supplier_credit_note",
        target_id=str(row.id),
        request=request,
        extra={
            "supplier_id":       str(body.supplier_id),
            "purchase_order_id": (
                str(body.purchase_order_id)
                if body.purchase_order_id else None
            ),
            "total":             str(totals.total),
        },
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.get(
    "/{supplier_credit_note_id}", response_model=SupplierCreditNoteOut,
)
async def get_supplier_credit_note(
    supplier_credit_note_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _user, member = ctx
    row = await _load(
        db, scn_id=supplier_credit_note_id, org_id=member.org_id,
    )
    return _to_out(row)


@router.patch(
    "/{supplier_credit_note_id}", response_model=SupplierCreditNoteOut,
)
async def update_supplier_credit_note(
    supplier_credit_note_id: uuid.UUID,
    body:    SupplierCreditNoteUpdate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(
        db, scn_id=supplier_credit_note_id, org_id=member.org_id,
    )
    if row.status is not SupplierCreditNoteStatus.DRAFT:
        raise HTTPException(
            status_code=409,
            detail="only DRAFT supplier credit notes may be edited",
        )

    changes: dict = {}
    try:
        if body.currency is not None:
            row.currency = svc_92.validate_currency(body.currency)
            changes["currency"] = row.currency
        if body.reason is not None:
            row.reason = svc_92.validate_reason(body.reason)
            changes["reason"] = "set"
        if body.issue_date is not None:
            row.issue_date = svc_92.validate_issue_date(body.issue_date)
            changes["issue_date"] = row.issue_date.isoformat()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if body.purchase_order_id is not None:
        await _assert_po_belongs(
            db,
            purchase_order_id=body.purchase_order_id,
            org_id=member.org_id,
            expected_supplier_id=row.supplier_id,
        )
        row.purchase_order_id = body.purchase_order_id
        changes["purchase_order_id"] = str(body.purchase_order_id)

    if body.lines is not None:
        lines = _validate_lines(body.lines)
        _replace_lines(row, lines)
        changes["lines"] = len(lines)

    await db.flush()
    await log_action(
        db,
        action="supplier_credit_note.updated",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="supplier_credit_note",
        target_id=str(row.id),
        request=request,
        extra=changes,
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.delete(
    "/{supplier_credit_note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_supplier_credit_note(
    supplier_credit_note_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(
        db, scn_id=supplier_credit_note_id, org_id=member.org_id,
    )
    if row.status is not SupplierCreditNoteStatus.DRAFT:
        raise HTTPException(
            status_code=409,
            detail="only DRAFT supplier credit notes may be deleted",
        )
    await db.delete(row)
    await log_action(
        db,
        action="supplier_credit_note.deleted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="supplier_credit_note",
        target_id=str(supplier_credit_note_id),
        request=request,
    )
    await db.commit()


async def _existing_credit_for_po(
    db: AsyncSession, *, purchase_order_id: uuid.UUID, org_id: uuid.UUID,
    exclude_id: uuid.UUID,
) -> Decimal:
    res = await db.execute(
        select(func.coalesce(func.sum(SupplierCreditNote.total), 0)).where(
            SupplierCreditNote.org_id == org_id,
            SupplierCreditNote.purchase_order_id == purchase_order_id,
            SupplierCreditNote.status == SupplierCreditNoteStatus.ISSUED,
            SupplierCreditNote.id != exclude_id,
        )
    )
    return Decimal(res.scalar() or 0)


@router.post(
    "/{supplier_credit_note_id}/issue",
    response_model=SupplierCreditNoteOut,
)
async def issue_supplier_credit_note(
    supplier_credit_note_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx

    await db.execute(
        select(Organization.id)
        .where(Organization.id == member.org_id)
        .with_for_update()
    )

    row = await _load(
        db, scn_id=supplier_credit_note_id, org_id=member.org_id,
    )
    try:
        svc_92.assert_transition(row.status, SupplierCreditNoteStatus.ISSUED)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    if not row.lines:
        raise HTTPException(
            status_code=400, detail="supplier credit note has no lines",
        )

    if row.purchase_order_id is not None:
        po = await db.get(PurchaseOrder, row.purchase_order_id)
        if po is None or po.org_id != member.org_id:
            raise HTTPException(
                status_code=404, detail="source purchase order missing",
            )
        other = await _existing_credit_for_po(
            db,
            purchase_order_id=row.purchase_order_id,
            org_id=member.org_id,
            exclude_id=row.id,
        )
        try:
            svc_92.assert_fits_po(
                credit_total=row.total,
                po_total=po.total,
                po_credited=other,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    year = row.issue_date.year
    used_rows = await db.execute(
        select(SupplierCreditNote.number).where(
            SupplierCreditNote.org_id == member.org_id,
            SupplierCreditNote.number.isnot(None),
        )
    )
    used = {n for (n,) in used_rows.all()}
    number = svc_92.next_number(year=year, existing=used)

    row.number = number
    row.status = SupplierCreditNoteStatus.ISSUED
    row.issued_at = datetime.now(tz=timezone.utc)

    await db.flush()
    await log_action(
        db,
        action="supplier_credit_note.issued",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="supplier_credit_note",
        target_id=str(row.id),
        request=request,
        extra={"number": number, "total": str(row.total)},
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.post(
    "/{supplier_credit_note_id}/void",
    response_model=SupplierCreditNoteOut,
)
async def void_supplier_credit_note(
    supplier_credit_note_id: uuid.UUID,
    body:    VoidBody,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(
        db, scn_id=supplier_credit_note_id, org_id=member.org_id,
    )
    try:
        svc_92.assert_transition(row.status, SupplierCreditNoteStatus.VOIDED)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    reason = (body.reason or "").strip()
    if not reason:
        raise HTTPException(
            status_code=400, detail="void reason is required",
        )
    if len(reason) > svc_92.MAX_REASON_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"reason too long ({svc_92.MAX_REASON_LENGTH} max)",
        )

    prev_status = row.status
    row.status = SupplierCreditNoteStatus.VOIDED
    row.voided_at = datetime.now(tz=timezone.utc)
    row.void_reason = reason

    await db.flush()
    await log_action(
        db,
        action="supplier_credit_note.voided",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="supplier_credit_note",
        target_id=str(row.id),
        request=request,
        extra={"from": prev_status.value, "reason": reason},
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)
