"""Mileage logs router (Item 98).

Endpoints under ``/api/mileage-logs``:

    GET    ""                 list logs (filters: from_date, to_date,
                              only_unconverted)
    POST   ""                 create
    GET    /summary           totals over a date range
    GET    /{log_id}          detail
    PATCH  /{log_id}          edit (rejects edits once converted)
    DELETE /{log_id}          delete (does not touch the linked Expense)
    POST   /{log_id}/convert  mint a DRAFT Expense and link back

A converted log is locked from edits. Deleting a converted log just
unlinks (CASCADE was deliberately not used on ``expense_id`` — the
generated expense outlives its mileage source for the audit trail).
"""
from __future__ import annotations

import logging
import uuid
from datetime import date as _date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.expenses import Expense, ExpenseCategory, ExpenseStatus
from app.models.mileage_log import MileageLog
from app.services import mileage as svc_98
from app.services.audit import log_action
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/mileage-logs", tags=["mileage-logs"], dependencies=[Depends(require_module("hr"))])

log = logging.getLogger(__name__)


# ── request / response ──────────────────────────────────────────────────


class LogCreate(BaseModel):
    trip_date:   _date
    distance_km: str
    rate_per_km: str
    currency:    str = "SEK"
    category_id: uuid.UUID | None = None
    origin:      str | None = None
    destination: str | None = None
    purpose:     str | None = None
    vehicle:     str | None = None


class LogUpdate(BaseModel):
    trip_date:   _date | None = None
    distance_km: str | None = None
    rate_per_km: str | None = None
    currency:    str | None = None
    category_id: uuid.UUID | None = None
    origin:      str | None = None
    destination: str | None = None
    purpose:     str | None = None
    vehicle:     str | None = None


class LogOut(BaseModel):
    id:           uuid.UUID
    trip_date:    _date
    distance_km:  str
    rate_per_km:  str
    amount:       str
    currency:     str
    category_id:  uuid.UUID | None
    origin:       str | None
    destination:  str | None
    purpose:      str | None
    vehicle:      str | None
    expense_id:   uuid.UUID | None
    converted_at: datetime | None
    created_at:   datetime
    updated_at:   datetime


class ConvertOut(BaseModel):
    expense_id: uuid.UUID


class SummaryOut(BaseModel):
    trip_count:   int
    total_km:     str
    total_amount: str
    currency:     str | None


# ── helpers ─────────────────────────────────────────────────────────────


def _to_out(row: MileageLog) -> LogOut:
    return LogOut(
        id=row.id,
        trip_date=row.trip_date,
        distance_km=str(row.distance_km),
        rate_per_km=str(row.rate_per_km),
        amount=str(row.amount),
        currency=row.currency,
        category_id=row.category_id,
        origin=row.origin,
        destination=row.destination,
        purpose=row.purpose,
        vehicle=row.vehicle,
        expense_id=row.expense_id,
        converted_at=row.converted_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _load(
    db: AsyncSession, *, log_id: uuid.UUID, org_id: uuid.UUID,
) -> MileageLog:
    row = await db.get(MileageLog, log_id)
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Mileage log not found")
    return row


async def _assert_category_belongs(
    db: AsyncSession, *, category_id: uuid.UUID | None, org_id: uuid.UUID,
) -> None:
    if category_id is None:
        return
    found = await db.scalar(
        select(ExpenseCategory.id).where(
            ExpenseCategory.id == category_id,
            ExpenseCategory.org_id == org_id,
        )
    )
    if found is None:
        raise HTTPException(status_code=404, detail="Category not found")


# ── endpoints ───────────────────────────────────────────────────────────


@router.get("", response_model=list[LogOut])
async def list_logs(
    from_date:        _date | None = Query(default=None),
    to_date:          _date | None = Query(default=None),
    only_unconverted: bool = Query(default=False),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    if from_date is not None and to_date is not None and to_date < from_date:
        raise HTTPException(
            status_code=400, detail="to_date must be >= from_date",
        )
    stmt = select(MileageLog).where(MileageLog.org_id == member.org_id)
    if from_date is not None:
        stmt = stmt.where(MileageLog.trip_date >= from_date)
    if to_date is not None:
        stmt = stmt.where(MileageLog.trip_date <= to_date)
    if only_unconverted:
        stmt = stmt.where(MileageLog.expense_id.is_(None))
    stmt = stmt.order_by(MileageLog.trip_date.desc(), MileageLog.created_at.desc())
    rows = (await db.scalars(stmt)).all()
    return [_to_out(r) for r in rows]


@router.get("/summary", response_model=SummaryOut)
async def summary(
    from_date: _date | None = Query(default=None),
    to_date:   _date | None = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    if from_date is not None and to_date is not None and to_date < from_date:
        raise HTTPException(
            status_code=400, detail="to_date must be >= from_date",
        )
    stmt = select(
        MileageLog.distance_km, MileageLog.amount, MileageLog.currency,
    ).where(MileageLog.org_id == member.org_id)
    if from_date is not None:
        stmt = stmt.where(MileageLog.trip_date >= from_date)
    if to_date is not None:
        stmt = stmt.where(MileageLog.trip_date <= to_date)
    rows = (await db.execute(stmt)).all()
    triples = [(r[0], r[1], r[2]) for r in rows]
    s = svc_98.summarize(triples)
    return SummaryOut(
        trip_count=s.trip_count,
        total_km=str(s.total_km),
        total_amount=str(s.total_amount),
        currency=s.currency,
    )


@router.post("", response_model=LogOut, status_code=status.HTTP_201_CREATED)
async def create_log(
    body:    LogCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    try:
        trip_date   = svc_98.validate_trip_date(body.trip_date)
        distance    = svc_98.validate_distance(body.distance_km)
        rate        = svc_98.validate_rate(body.rate_per_km)
        currency    = svc_98.validate_currency(body.currency)
        origin      = svc_98.validate_origin(body.origin)
        destination = svc_98.validate_destination(body.destination)
        purpose     = svc_98.validate_purpose(body.purpose)
        vehicle     = svc_98.validate_vehicle(body.vehicle)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await _assert_category_belongs(
        db, category_id=body.category_id, org_id=member.org_id,
    )
    amount = svc_98.compute_amount(distance_km=distance, rate_per_km=rate)

    row = MileageLog(
        org_id=member.org_id,
        created_by_user_id=uuid.UUID(user["user_id"]),
        trip_date=trip_date,
        distance_km=distance,
        rate_per_km=rate,
        amount=amount,
        currency=currency,
        category_id=body.category_id,
        origin=origin,
        destination=destination,
        purpose=purpose,
        vehicle=vehicle,
    )
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="mileage_log.created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="mileage_log",
        target_id=str(row.id),
        request=request,
        extra={
            "trip_date": trip_date.isoformat(),
            "distance_km": str(distance),
            "amount": str(amount),
        },
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.get("/{log_id}", response_model=LogOut)
async def get_log(
    log_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    row = await _load(db, log_id=log_id, org_id=member.org_id)
    return _to_out(row)


@router.patch("/{log_id}", response_model=LogOut)
async def update_log(
    log_id:  uuid.UUID,
    body:    LogUpdate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, log_id=log_id, org_id=member.org_id)
    if row.expense_id is not None:
        raise HTTPException(
            status_code=409,
            detail="log has been converted — edit the linked expense instead",
        )

    changed: dict[str, object] = {}
    try:
        if body.trip_date is not None:
            v = svc_98.validate_trip_date(body.trip_date)
            if v != row.trip_date:
                row.trip_date = v
                changed["trip_date"] = v.isoformat()
        if body.distance_km is not None:
            v = svc_98.validate_distance(body.distance_km)
            if v != row.distance_km:
                row.distance_km = v
                changed["distance_km"] = str(v)
        if body.rate_per_km is not None:
            v = svc_98.validate_rate(body.rate_per_km)
            if v != row.rate_per_km:
                row.rate_per_km = v
                changed["rate_per_km"] = str(v)
        if body.currency is not None:
            v = svc_98.validate_currency(body.currency)
            if v != row.currency:
                row.currency = v
                changed["currency"] = v
        if body.origin is not None:
            row.origin = svc_98.validate_origin(body.origin)
            changed["origin"] = True
        if body.destination is not None:
            row.destination = svc_98.validate_destination(body.destination)
            changed["destination"] = True
        if body.purpose is not None:
            row.purpose = svc_98.validate_purpose(body.purpose)
            changed["purpose"] = True
        if body.vehicle is not None:
            row.vehicle = svc_98.validate_vehicle(body.vehicle)
            changed["vehicle"] = True
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if body.category_id is not None:
        await _assert_category_belongs(
            db, category_id=body.category_id, org_id=member.org_id,
        )
        row.category_id = body.category_id
        changed["category_id"] = str(body.category_id)

    # Recompute the denormalised amount whenever distance OR rate
    # changed.
    if "distance_km" in changed or "rate_per_km" in changed:
        row.amount = svc_98.compute_amount(
            distance_km=row.distance_km, rate_per_km=row.rate_per_km,
        )
        changed["amount"] = str(row.amount)

    await log_action(
        db,
        action="mileage_log.updated",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="mileage_log",
        target_id=str(row.id),
        request=request,
        extra={"changed": changed},
    )
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_log(
    log_id:  uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, log_id=log_id, org_id=member.org_id)
    expense_id = row.expense_id
    await db.delete(row)
    await log_action(
        db,
        action="mileage_log.deleted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="mileage_log",
        target_id=str(log_id),
        request=request,
        extra={
            "had_expense_id": str(expense_id) if expense_id else None,
        },
    )
    await db.commit()


@router.post("/{log_id}/convert", response_model=ConvertOut)
async def convert_log(
    log_id:  uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, log_id=log_id, org_id=member.org_id)
    if row.expense_id is not None:
        raise HTTPException(
            status_code=409, detail="log already converted",
        )
    if row.approval_status != "approved":
        raise HTTPException(
            status_code=409, detail="log must be approved before conversion",
        )

    description_bits: list[str] = []
    if row.origin or row.destination:
        description_bits.append(
            f"{row.origin or '?'} → {row.destination or '?'}"
        )
    description_bits.append(
        f"{row.distance_km} km × {row.rate_per_km}"
    )
    if row.purpose:
        description_bits.append(row.purpose)
    description = " | ".join(description_bits)

    expense = Expense(
        org_id=member.org_id,
        created_by=uuid.UUID(user["user_id"]),
        category_id=row.category_id,
        amount=row.amount,
        currency=row.currency,
        description=description,
        expense_date=row.trip_date,
        status=ExpenseStatus.DRAFT,
    )
    db.add(expense)
    await db.flush()

    row.expense_id = expense.id
    row.converted_at = datetime.now(timezone.utc)

    await log_action(
        db,
        action="mileage_log.converted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="mileage_log",
        target_id=str(row.id),
        request=request,
        extra={"expense_id": str(expense.id)},
    )
    await db.commit()
    return ConvertOut(expense_id=expense.id)


# ── Approval endpoints ─────────────────────────────────────────────────
@router.post("/{log_id}/approve")
async def approve_mileage_log(
    log_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    role = getattr(member, "role", None) or "MEMBER"
    if role not in ("OWNER", "ADMIN"):
        raise HTTPException(status_code=403, detail="Only managers can approve")
    row = await _load(db, log_id=log_id, org_id=member.org_id)
    if row.approval_status != "pending":
        raise HTTPException(status_code=409, detail="Already reviewed")
    row.approval_status = "approved"
    row.approved_by = uuid.UUID(user["user_id"]) if "user_id" in user else None
    row.approved_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "approved"}


@router.post("/{log_id}/reject")
async def reject_mileage_log(
    log_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    role = getattr(member, "role", None) or "MEMBER"
    if role not in ("OWNER", "ADMIN"):
        raise HTTPException(status_code=403, detail="Only managers can reject")
    row = await _load(db, log_id=log_id, org_id=member.org_id)
    if row.approval_status != "pending":
        raise HTTPException(status_code=409, detail="Already reviewed")
    row.approval_status = "rejected"
    row.approved_by = uuid.UUID(user["user_id"]) if "user_id" in user else None
    row.approved_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "rejected"}
