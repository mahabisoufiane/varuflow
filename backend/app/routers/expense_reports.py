"""Expense reports router (Item 100).

Endpoints under ``/api/expense-reports``:

    GET    ""                                list
    POST   ""                                create (DRAFT)
    GET    /{report_id}                      detail (+ items + totals)
    PATCH  /{report_id}                      edit (DRAFT/REJECTED only)
    DELETE /{report_id}                      delete (DRAFT/REJECTED only)
    POST   /{report_id}/items                add an expense to the report
    DELETE /{report_id}/items/{expense_id}   remove
    POST   /{report_id}/submit               DRAFT → SUBMITTED
    POST   /{report_id}/approve              SUBMITTED → APPROVED  (owner/admin)
    POST   /{report_id}/reject               SUBMITTED → REJECTED  (owner/admin)
    POST   /{report_id}/mark-paid            APPROVED → PAID       (owner/admin)

State machine lives in the pure service (`svc_100.can_transition`).
Items can only be added/removed while the report is DRAFT.

Authorisation:
* Owner of the report (creator) can edit items, submit, mark-paid.
* approve / reject require OWNER or ADMIN role.
* mark-paid requires OWNER or ADMIN role (the finance gate).

Adding an expense requires: the expense belongs to the same org, is
not already on another report (enforced by the unique index +
pre-check), and has status APPROVED — only approved expenses are
reimbursable.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.expense_report import (
    ExpenseReport, ExpenseReportItem, ExpenseReportStatus,
)
from app.models.expenses import Expense, ExpenseStatus
from app.models.organization import OrgRole
from app.services import expense_report as svc_100
from app.services.audit import log_action

router = APIRouter(prefix="/api/expense-reports", tags=["expense-reports"], dependencies=[Depends(require_module("finance"))])

log = logging.getLogger(__name__)


# ── request / response ─────────────────────────────────────────────────


class ReportCreate(BaseModel):
    title:    str
    currency: str = "SEK"
    note:     str | None = None


class ReportUpdate(BaseModel):
    title:    str | None = None
    currency: str | None = None
    note:     str | None = None


class ReportOut(BaseModel):
    id:                  uuid.UUID
    title:               str
    currency:            str
    status:              str
    note:                str | None
    submitted_at:        datetime | None
    decided_at:          datetime | None
    decided_by_user_id:  uuid.UUID | None
    review_note:         str | None
    paid_at:             datetime | None
    paid_reference:      str | None
    item_count:          int
    total_amount:        str
    created_by_user_id:  uuid.UUID
    created_at:          datetime
    updated_at:          datetime


class ItemOut(BaseModel):
    expense_id: uuid.UUID
    amount:     str
    currency:   str
    added_at:   datetime


class ReportDetail(BaseModel):
    report: ReportOut
    items:  list[ItemOut]


class AddItemIn(BaseModel):
    expense_id: uuid.UUID


class DecisionIn(BaseModel):
    review_note: str | None = None


class MarkPaidIn(BaseModel):
    paid_reference: str | None = None


# ── helpers ────────────────────────────────────────────────────────────


def _status_str(row: ExpenseReport) -> str:
    return (
        row.status.value if isinstance(row.status, ExpenseReportStatus)
        else str(row.status)
    )


async def _compute_totals(
    db: AsyncSession, *, report_id: uuid.UUID,
) -> tuple[int, Decimal]:
    rows = (await db.execute(
        select(Expense.amount)
        .join(
            ExpenseReportItem,
            ExpenseReportItem.expense_id == Expense.id,
        )
        .where(ExpenseReportItem.report_id == report_id)
    )).scalars().all()
    amounts = [Decimal(str(r)) for r in rows]
    t = svc_100.compute_totals(amounts)
    return t.item_count, t.total


def _to_out(
    row: ExpenseReport, *, item_count: int, total_amount: Decimal,
) -> ReportOut:
    return ReportOut(
        id=row.id,
        title=row.title,
        currency=row.currency,
        status=_status_str(row),
        note=row.note,
        submitted_at=row.submitted_at,
        decided_at=row.decided_at,
        decided_by_user_id=row.decided_by_user_id,
        review_note=row.review_note,
        paid_at=row.paid_at,
        paid_reference=row.paid_reference,
        item_count=item_count,
        total_amount=str(total_amount),
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _load(
    db: AsyncSession, *, report_id: uuid.UUID, org_id: uuid.UUID,
) -> ExpenseReport:
    row = await db.get(ExpenseReport, report_id)
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Report not found")
    return row


def _require_owner_or_admin(member) -> None:
    if member.role not in (OrgRole.OWNER, OrgRole.ADMIN):
        raise HTTPException(
            status_code=403, detail="only_owner_or_admin",
        )


def _require_author_or_owner(row: ExpenseReport, member, actor_uid: uuid.UUID) -> None:
    """Creator can mutate their own report; owner/admin can mutate
    anyone's. MEMBER role touching someone else's report → 403.
    """
    if member.role in (OrgRole.OWNER, OrgRole.ADMIN):
        return
    if row.created_by_user_id != actor_uid:
        raise HTTPException(
            status_code=403, detail="not_report_author",
        )


async def _transition(
    row: ExpenseReport, *, to_status: str,
) -> None:
    from_s = _status_str(row)
    try:
        svc_100.assert_transition(from_status=from_s, to_status=to_status)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    row.status = ExpenseReportStatus(to_status)


# ── endpoints ──────────────────────────────────────────────────────────


@router.get("", response_model=list[ReportOut])
async def list_reports(
    status_: str | None = Query(default=None, alias="status"),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    stmt = select(ExpenseReport).where(
        ExpenseReport.org_id == member.org_id,
    )
    if status_ is not None:
        try:
            s = svc_100.validate_status(status_)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        stmt = stmt.where(
            ExpenseReport.status == ExpenseReportStatus(s),
        )
    stmt = stmt.order_by(ExpenseReport.created_at.desc())
    rows = (await db.scalars(stmt)).all()
    out: list[ReportOut] = []
    for r in rows:
        count, total = await _compute_totals(db, report_id=r.id)
        out.append(_to_out(r, item_count=count, total_amount=total))
    return out


@router.post("", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
async def create_report(
    body:    ReportCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    try:
        title    = svc_100.validate_title(body.title)
        currency = svc_100.validate_currency(body.currency)
        note     = svc_100.validate_note(body.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    row = ExpenseReport(
        org_id=member.org_id,
        created_by_user_id=uuid.UUID(user["user_id"]),
        title=title,
        currency=currency,
        status=ExpenseReportStatus.DRAFT,
        note=note,
    )
    db.add(row)
    await db.flush()

    await log_action(
        db,
        action="expense_report.created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="expense_report",
        target_id=str(row.id),
        request=request,
        extra={"title": title, "currency": currency},
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row, item_count=0, total_amount=Decimal("0.00"))


@router.get("/{report_id}", response_model=ReportDetail)
async def get_report(
    report_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    row = await _load(db, report_id=report_id, org_id=member.org_id)
    # Items — joined with the expense to surface amount/currency.
    rows = (await db.execute(
        select(
            ExpenseReportItem.expense_id,
            Expense.amount,
            Expense.currency,
            ExpenseReportItem.added_at,
        )
        .join(Expense, Expense.id == ExpenseReportItem.expense_id)
        .where(ExpenseReportItem.report_id == report_id)
        .order_by(ExpenseReportItem.added_at.asc())
    )).all()
    items = [
        ItemOut(
            expense_id=r[0],
            amount=str(r[1]),
            currency=r[2],
            added_at=r[3],
        )
        for r in rows
    ]
    count, total = await _compute_totals(db, report_id=report_id)
    return ReportDetail(
        report=_to_out(row, item_count=count, total_amount=total),
        items=items,
    )


@router.patch("/{report_id}", response_model=ReportOut)
async def update_report(
    report_id: uuid.UUID,
    body:      ReportUpdate,
    request:   Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, report_id=report_id, org_id=member.org_id)
    actor_uid = uuid.UUID(user["user_id"])
    _require_author_or_owner(row, member, actor_uid)

    current = _status_str(row)
    if current not in (svc_100.STATUS_DRAFT, svc_100.STATUS_REJECTED):
        raise HTTPException(
            status_code=409,
            detail=f"cannot edit report in status {current}",
        )

    changed: dict[str, object] = {}
    try:
        if body.title is not None:
            v = svc_100.validate_title(body.title)
            if v != row.title:
                row.title = v
                changed["title"] = v
        if body.currency is not None:
            v = svc_100.validate_currency(body.currency)
            if v != row.currency:
                row.currency = v
                changed["currency"] = v
        if body.note is not None:
            row.note = svc_100.validate_note(body.note)
            changed["note"] = True
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await log_action(
        db,
        action="expense_report.updated",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="expense_report",
        target_id=str(row.id),
        request=request,
        extra={"changed": changed},
    )
    await db.commit()
    await db.refresh(row)
    count, total = await _compute_totals(db, report_id=report_id)
    return _to_out(row, item_count=count, total_amount=total)


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: uuid.UUID,
    request:   Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, report_id=report_id, org_id=member.org_id)
    actor_uid = uuid.UUID(user["user_id"])
    _require_author_or_owner(row, member, actor_uid)

    current = _status_str(row)
    if current not in (svc_100.STATUS_DRAFT, svc_100.STATUS_REJECTED):
        raise HTTPException(
            status_code=409,
            detail=f"cannot delete report in status {current}",
        )
    await db.delete(row)
    await log_action(
        db,
        action="expense_report.deleted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="expense_report",
        target_id=str(report_id),
        request=request,
        extra={"title": row.title},
    )
    await db.commit()


# ── items ──────────────────────────────────────────────────────────────


@router.post(
    "/{report_id}/items",
    response_model=ItemOut, status_code=status.HTTP_201_CREATED,
)
async def add_item(
    report_id: uuid.UUID,
    body:      AddItemIn,
    request:   Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, report_id=report_id, org_id=member.org_id)
    actor_uid = uuid.UUID(user["user_id"])
    _require_author_or_owner(row, member, actor_uid)

    current = _status_str(row)
    if not svc_100.items_mutable_in(current):
        raise HTTPException(
            status_code=409,
            detail=f"cannot modify items in status {current}",
        )

    # Expense must belong to the same org AND be APPROVED AND not
    # already on another report.
    expense = await db.get(Expense, body.expense_id)
    if expense is None or expense.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="Expense not found")
    if expense.status != ExpenseStatus.APPROVED:
        raise HTTPException(
            status_code=400,
            detail="only APPROVED expenses can be added to a report",
        )
    if expense.currency != row.currency:
        raise HTTPException(
            status_code=400,
            detail="expense currency does not match report currency",
        )

    item = ExpenseReportItem(
        report_id=row.id, expense_id=body.expense_id,
    )
    db.add(item)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="expense already belongs to a report",
        )

    await log_action(
        db,
        action="expense_report.item_added",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="expense_report",
        target_id=str(row.id),
        request=request,
        extra={"expense_id": str(body.expense_id)},
    )
    await db.commit()
    await db.refresh(item)
    return ItemOut(
        expense_id=item.expense_id,
        amount=str(expense.amount),
        currency=expense.currency,
        added_at=item.added_at,
    )


@router.delete(
    "/{report_id}/items/{expense_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_item(
    report_id:  uuid.UUID,
    expense_id: uuid.UUID,
    request:    Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, report_id=report_id, org_id=member.org_id)
    actor_uid = uuid.UUID(user["user_id"])
    _require_author_or_owner(row, member, actor_uid)

    current = _status_str(row)
    if not svc_100.items_mutable_in(current):
        raise HTTPException(
            status_code=409,
            detail=f"cannot modify items in status {current}",
        )

    item = await db.scalar(
        select(ExpenseReportItem).where(
            ExpenseReportItem.report_id == row.id,
            ExpenseReportItem.expense_id == expense_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.delete(item)
    await log_action(
        db,
        action="expense_report.item_removed",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="expense_report",
        target_id=str(row.id),
        request=request,
        extra={"expense_id": str(expense_id)},
    )
    await db.commit()


# ── state transitions ──────────────────────────────────────────────────


@router.post("/{report_id}/submit", response_model=ReportOut)
async def submit_report(
    report_id: uuid.UUID,
    request:   Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, report_id=report_id, org_id=member.org_id)
    actor_uid = uuid.UUID(user["user_id"])
    _require_author_or_owner(row, member, actor_uid)

    # Empty reports can't be submitted — force at least one item.
    count, _ = await _compute_totals(db, report_id=report_id)
    if count == 0:
        raise HTTPException(
            status_code=400, detail="report has no items",
        )

    await _transition(row, to_status=svc_100.STATUS_SUBMITTED)
    row.submitted_at = datetime.now(timezone.utc)

    await log_action(
        db,
        action="expense_report.submitted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="expense_report",
        target_id=str(row.id),
        request=request,
        extra={"item_count": count},
    )
    await db.commit()
    await db.refresh(row)
    count, total = await _compute_totals(db, report_id=report_id)
    return _to_out(row, item_count=count, total_amount=total)


@router.post("/{report_id}/approve", response_model=ReportOut)
async def approve_report(
    report_id: uuid.UUID,
    body:      DecisionIn,
    request:   Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    _require_owner_or_admin(member)
    row = await _load(db, report_id=report_id, org_id=member.org_id)
    try:
        review_note = svc_100.validate_review_note(body.review_note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await _transition(row, to_status=svc_100.STATUS_APPROVED)
    row.decided_at = datetime.now(timezone.utc)
    row.decided_by_user_id = uuid.UUID(user["user_id"])
    row.review_note = review_note

    await log_action(
        db,
        action="expense_report.approved",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="expense_report",
        target_id=str(row.id),
        request=request,
    )
    await db.commit()
    await db.refresh(row)
    count, total = await _compute_totals(db, report_id=report_id)
    return _to_out(row, item_count=count, total_amount=total)


@router.post("/{report_id}/reject", response_model=ReportOut)
async def reject_report(
    report_id: uuid.UUID,
    body:      DecisionIn,
    request:   Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    _require_owner_or_admin(member)
    row = await _load(db, report_id=report_id, org_id=member.org_id)
    try:
        review_note = svc_100.validate_review_note(body.review_note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await _transition(row, to_status=svc_100.STATUS_REJECTED)
    row.decided_at = datetime.now(timezone.utc)
    row.decided_by_user_id = uuid.UUID(user["user_id"])
    row.review_note = review_note

    await log_action(
        db,
        action="expense_report.rejected",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="expense_report",
        target_id=str(row.id),
        request=request,
    )
    await db.commit()
    await db.refresh(row)
    count, total = await _compute_totals(db, report_id=report_id)
    return _to_out(row, item_count=count, total_amount=total)


@router.post("/{report_id}/mark-paid", response_model=ReportOut)
async def mark_paid(
    report_id: uuid.UUID,
    body:      MarkPaidIn,
    request:   Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    _require_owner_or_admin(member)
    row = await _load(db, report_id=report_id, org_id=member.org_id)
    try:
        reference = svc_100.validate_paid_reference(body.paid_reference)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await _transition(row, to_status=svc_100.STATUS_PAID)
    row.paid_at = datetime.now(timezone.utc)
    row.paid_reference = reference

    await log_action(
        db,
        action="expense_report.paid",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="expense_report",
        target_id=str(row.id),
        request=request,
        extra={"paid_reference": reference},
    )
    await db.commit()
    await db.refresh(row)
    count, total = await _compute_totals(db, report_id=report_id)
    return _to_out(row, item_count=count, total_amount=total)
