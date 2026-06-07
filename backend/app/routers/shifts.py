"""Shifts & payroll router (Item 67).

Endpoints under ``/api/shifts``:

    GET    ""                      list shifts in a range
    POST   ""                      create a shift
    PATCH  /{shift_id}              edit a shift
    DELETE /{shift_id}              delete a shift
    POST   /{shift_id}/clock-in     open a punch (staff themselves)
    POST   /{shift_id}/clock-out    close the open punch
    GET    /payroll.csv             per-staff aggregated payroll export

All times are timezone-aware UTC. Overlap detection fires a 409
before a UNIQUE trip.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.bookings import Staff
from app.models.shift import Shift, ShiftPunch, RosterPublication
from app.models.shift_swap import ShiftSwapRequest
from app.services import shift as svc
from app.services.audit import log_action

router = APIRouter(prefix="/api/shifts", tags=["shifts"], dependencies=[Depends(require_module("hr"))])

log = logging.getLogger(__name__)

_MIN_REST_HOURS = 11


def _iso_week(dt: datetime) -> str:
    """Return ISO week string like '2026-W18'."""
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


async def _check_rest_period(
    db: AsyncSession, org_id, staff_id, start_at: datetime, end_at: datetime,
    exclude_id=None, force: bool = False,
):
    """Enforce EU Working Time Directive 11h minimum rest between shifts."""
    from sqlalchemy import and_, or_
    conditions = [Shift.org_id == org_id, Shift.staff_id == staff_id]
    if exclude_id:
        conditions.append(Shift.id != exclude_id)
    others = (await db.execute(select(Shift).where(*conditions))).scalars().all()
    for other in others:
        # Gap between this shift end and other start
        if other.start_at > end_at:
            gap = (other.start_at - end_at).total_seconds() / 3600
            if gap < _MIN_REST_HOURS:
                if force:
                    return  # allow with warning
                raise HTTPException(
                    status_code=409,
                    detail=f"Minimum {_MIN_REST_HOURS}h rest period violated (gap: {gap:.1f}h before next shift)",
                )
        # Gap between other end and this shift start
        if other.end_at < start_at:
            gap = (start_at - other.end_at).total_seconds() / 3600
            if gap < _MIN_REST_HOURS:
                if force:
                    return
                raise HTTPException(
                    status_code=409,
                    detail=f"Minimum {_MIN_REST_HOURS}h rest period violated (gap: {gap:.1f}h after previous shift)",
                )



class ShiftCreate(BaseModel):
    staff_id:    uuid.UUID
    start_at:    datetime
    end_at:      datetime
    hourly_rate: Decimal | None = None
    notes:       str | None = None
    color:       str | None = None
    roster_week: str | None = None


class ShiftUpdate(BaseModel):
    start_at:    datetime | None = None
    end_at:      datetime | None = None
    hourly_rate: Decimal | None = None
    notes:       str | None = None
    color:       str | None = None
    roster_week: str | None = None


class ShiftOut(BaseModel):
    id:          uuid.UUID
    staff_id:    uuid.UUID
    start_at:    datetime
    end_at:      datetime
    hourly_rate: Decimal | None
    notes:       str | None
    color:       str | None = None
    roster_week: str | None = None


class PunchOut(BaseModel):
    id:           uuid.UUID
    shift_id:     uuid.UUID
    staff_id:     uuid.UUID
    clock_in_at:  datetime
    clock_out_at: datetime | None


async def _load_shift(
    db: AsyncSession, *, shift_id: uuid.UUID, org_id: uuid.UUID
) -> Shift:
    row = await db.get(Shift, shift_id)
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Shift not found")
    return row


async def _assert_staff_in_org(
    db: AsyncSession, *, staff_id: uuid.UUID, org_id: uuid.UUID
) -> None:
    row = await db.scalar(
        select(Staff).where(Staff.id == staff_id, Staff.org_id == org_id)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Staff not found")


def _to_span(r: Shift) -> svc.ShiftSpan:
    return svc.ShiftSpan(
        id=str(r.id), staff_id=str(r.staff_id), start=r.start_at, end=r.end_at
    )


@router.get("", response_model=list[ShiftOut])
async def list_shifts(
    staff_id: uuid.UUID | None = Query(default=None),
    start:    datetime | None = Query(default=None),
    end:      datetime | None = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _user, member = ctx
    stmt = select(Shift).where(Shift.org_id == member.org_id)
    if staff_id is not None:
        stmt = stmt.where(Shift.staff_id == staff_id)
    if start is not None:
        stmt = stmt.where(Shift.end_at > start)
    if end is not None:
        stmt = stmt.where(Shift.start_at < end)
    stmt = stmt.order_by(Shift.start_at.asc())
    rows = (await db.scalars(stmt)).all()
    return list(rows)


@router.post("", response_model=ShiftOut, status_code=status.HTTP_201_CREATED)
async def create_shift(
    body: ShiftCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    await _assert_staff_in_org(db, staff_id=body.staff_id, org_id=member.org_id)
    try:
        s, e = svc.validate_shift_bounds(body.start_at, body.end_at)
        rate = svc.validate_hourly_rate(body.hourly_rate)
        notes = svc.validate_notes(body.notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Overlap guard — cheaper than a UNIQUE trip and gives a clean 409.
    existing = list(
        (
            await db.scalars(
                select(Shift).where(
                    Shift.org_id == member.org_id,
                    Shift.staff_id == body.staff_id,
                )
            )
        ).all()
    )
    candidate = svc.ShiftSpan(
        id="__new__", staff_id=str(body.staff_id), start=s, end=e
    )
    clash = svc.detect_overlap(candidate, [_to_span(r) for r in existing])
    if clash is not None:
        raise HTTPException(status_code=409, detail="shift overlaps existing")

    await _check_rest_period(db, member.org_id, body.staff_id, s, e)

    row = Shift(
        org_id=member.org_id,
        staff_id=body.staff_id,
        start_at=s,
        end_at=e,
        hourly_rate=rate,
        notes=notes,
        color=body.color,
        roster_week=body.roster_week or _iso_week(s),
    )
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="shift.created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="shift",
        target_id=str(row.id),
        request=request,
        extra={"staff_id": str(body.staff_id)},
    )
    await db.commit()
    await db.refresh(row)
    return row


@router.patch("/{shift_id}", response_model=ShiftOut)
async def update_shift(
    shift_id: uuid.UUID,
    body: ShiftUpdate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load_shift(db, shift_id=shift_id, org_id=member.org_id)

    new_start = body.start_at if body.start_at is not None else row.start_at
    new_end = body.end_at if body.end_at is not None else row.end_at
    changed: list[str] = []
    try:
        if body.start_at is not None or body.end_at is not None:
            s, e = svc.validate_shift_bounds(new_start, new_end)
            # Recheck overlap against the staff's other shifts.
            others = list(
                (
                    await db.scalars(
                        select(Shift).where(
                            Shift.org_id == member.org_id,
                            Shift.staff_id == row.staff_id,
                            Shift.id != row.id,
                        )
                    )
                ).all()
            )
            cand = svc.ShiftSpan(
                id=str(row.id), staff_id=str(row.staff_id), start=s, end=e
            )
            clash = svc.detect_overlap(cand, [_to_span(r) for r in others])
            if clash is not None:
                raise HTTPException(
                    status_code=409, detail="shift overlaps existing"
                )
            await _check_rest_period(db, member.org_id, row.staff_id, s, e, exclude_id=row.id)
            if body.start_at is not None:
                row.start_at = s; changed.append("start_at")
            if body.end_at is not None:
                row.end_at = e; changed.append("end_at")
        if body.hourly_rate is not None:
            row.hourly_rate = svc.validate_hourly_rate(body.hourly_rate)
            changed.append("hourly_rate")
        if body.notes is not None:
            row.notes = svc.validate_notes(body.notes); changed.append("notes")
        if body.color is not None:
            row.color = body.color; changed.append("color")
        if body.roster_week is not None:
            row.roster_week = body.roster_week; changed.append("roster_week")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if changed:
        await log_action(
            db,
            action="shift.updated",
            org_id=member.org_id,
            actor_user_id=user["user_id"],
            target_type="shift",
            target_id=str(row.id),
            request=request,
            extra={"fields": changed},
        )
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shift(
    shift_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load_shift(db, shift_id=shift_id, org_id=member.org_id)
    await db.delete(row)
    await log_action(
        db,
        action="shift.deleted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="shift",
        target_id=str(shift_id),
        request=request,
        extra={},
    )
    await db.commit()
    return None


@router.post("/{shift_id}/clock-in", response_model=PunchOut, status_code=status.HTTP_201_CREATED)
async def clock_in(
    shift_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load_shift(db, shift_id=shift_id, org_id=member.org_id)
    now = datetime.now(timezone.utc)
    open_count = len(
        list(
            (
                await db.scalars(
                    select(ShiftPunch).where(
                        ShiftPunch.shift_id == row.id,
                        ShiftPunch.clock_out_at.is_(None),
                    )
                )
            ).all()
        )
    )
    try:
        svc.open_punch(existing_open=open_count, shift_has_ended=row.end_at <= now)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    punch = ShiftPunch(
        org_id=member.org_id,
        shift_id=row.id,
        staff_id=row.staff_id,
        clock_in_at=now,
        clock_out_at=None,
    )
    db.add(punch)
    await db.flush()
    await log_action(
        db,
        action="shift.clock_in",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="shift_punch",
        target_id=str(punch.id),
        request=request,
        extra={"shift_id": str(row.id)},
    )
    await db.commit()
    await db.refresh(punch)
    return punch


@router.post("/{shift_id}/clock-out", response_model=PunchOut)
async def clock_out(
    shift_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load_shift(db, shift_id=shift_id, org_id=member.org_id)
    punch = (
        await db.scalars(
            select(ShiftPunch).where(
                ShiftPunch.shift_id == row.id,
                ShiftPunch.clock_out_at.is_(None),
            )
        )
    ).first()
    if punch is None:
        raise HTTPException(status_code=409, detail="no open punch")

    now = datetime.now(timezone.utc)
    try:
        svc.close_punch(punch.clock_in_at, now)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    punch.clock_out_at = now
    await log_action(
        db,
        action="shift.clock_out",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="shift_punch",
        target_id=str(punch.id),
        request=request,
        extra={"shift_id": str(row.id)},
    )
    await db.commit()
    await db.refresh(punch)
    return punch


@router.get("/payroll.csv")
async def payroll_csv(
    start: datetime = Query(...),
    end:   datetime = Query(...),
    ctx:   tuple = Depends(get_current_member),
    db:    AsyncSession = Depends(get_db),
):
    _user, member = ctx
    if end <= start:
        raise HTTPException(status_code=400, detail="end must be after start")
    punches = list(
        (
            await db.scalars(
                select(ShiftPunch).where(
                    ShiftPunch.org_id == member.org_id,
                    ShiftPunch.clock_out_at.isnot(None),
                    ShiftPunch.clock_in_at < end,
                    ShiftPunch.clock_out_at > start,
                )
            )
        ).all()
    )
    # Load rate from the matching shift (fall back to NULL).
    shift_ids = {p.shift_id for p in punches}
    rate_by_shift: dict[uuid.UUID, Decimal | None] = {}
    if shift_ids:
        shifts = list(
            (
                await db.scalars(
                    select(Shift).where(Shift.id.in_(shift_ids))
                )
            ).all()
        )
        rate_by_shift = {s.id: s.hourly_rate for s in shifts}

    tuples = [
        (
            str(p.staff_id),
            p.clock_in_at,
            p.clock_out_at,
            rate_by_shift.get(p.shift_id),
        )
        for p in punches
    ]
    try:
        rows = svc.aggregate_payroll(
            tuples, period_start=start, period_end=end
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    csv_text = svc.render_payroll_csv(rows)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="payroll.csv"'},
    )


# ── Roster endpoints ──────────────────────────────────────────────────────────

def _row_shift(r: Shift, staff_name: str = "") -> dict:
    return {
        "id": str(r.id),
        "staff_id": str(r.staff_id),
        "staff_name": staff_name,
        "start_at": r.start_at.isoformat(),
        "end_at": r.end_at.isoformat(),
        "hourly_rate": str(r.hourly_rate) if r.hourly_rate else None,
        "notes": r.notes,
        "color": r.color,
        "roster_week": r.roster_week,
    }


@router.get("/roster")
async def get_roster(
    week_start: date = Query(..., description="Monday of the week (YYYY-MM-DD)"),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _user, member = ctx
    try:
        week_end_dt = datetime(week_start.year, week_start.month, week_start.day, tzinfo=timezone.utc) + timedelta(days=7)
        week_start_dt = datetime(week_start.year, week_start.month, week_start.day, tzinfo=timezone.utc)

        shifts = (await db.scalars(
            select(Shift).where(
                and_(
                    Shift.org_id == member.org_id,
                    Shift.start_at >= week_start_dt,
                    Shift.start_at < week_end_dt,
                )
            ).order_by(Shift.start_at)
        )).all()

        staff_ids = {s.staff_id for s in shifts}
        staff_map: dict[str, str] = {}
        if staff_ids:
            staff_rows = (await db.scalars(select(Staff).where(Staff.id.in_(staff_ids)))).all()
            staff_map = {str(s.id): s.name for s in staff_rows}

        pub = (await db.scalar(
            select(RosterPublication).where(
                and_(
                    RosterPublication.org_id == member.org_id,
                    RosterPublication.week_start == week_start,
                )
            )
        ))

        return {
            "week_start": str(week_start),
            "published": pub is not None,
            "published_at": pub.published_at.isoformat() if pub else None,
            "shifts": [_row_shift(s, staff_map.get(str(s.staff_id), "")) for s in shifts],
        }
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"get_roster failed: {exc}", extra={"org_id": str(member.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/roster/publications")
async def list_publications(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _user, member = ctx
    try:
        rows = (await db.scalars(
            select(RosterPublication).where(RosterPublication.org_id == member.org_id)
            .order_by(RosterPublication.week_start.desc())
        )).all()
        return [{"week_start": str(r.week_start), "published_at": r.published_at.isoformat()} for r in rows]
    except Exception as exc:
        log.error(f"list_publications failed: {exc}", extra={"org_id": str(member.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/roster/copy-last-week", status_code=201)
async def copy_last_week(
    week_start: date = Query(...),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _user, member = ctx
    try:
        prev_start = datetime(week_start.year, week_start.month, week_start.day, tzinfo=timezone.utc) - timedelta(weeks=1)
        prev_end = prev_start + timedelta(days=7)
        this_start = datetime(week_start.year, week_start.month, week_start.day, tzinfo=timezone.utc)

        source_shifts = (await db.scalars(
            select(Shift).where(
                and_(
                    Shift.org_id == member.org_id,
                    Shift.start_at >= prev_start,
                    Shift.start_at < prev_end,
                )
            )
        )).all()

        if not source_shifts:
            raise HTTPException(status_code=422, detail="No shifts found in the previous week to copy")

        new_week_iso = _iso_week(this_start)
        created = 0
        skipped = 0
        for s in source_shifts:
            offset = s.start_at - prev_start
            new_start = this_start + offset
            new_end = new_start + (s.end_at - s.start_at)
            # Skip if exact duplicate already exists
            exists = await db.scalar(
                select(Shift.id).where(
                    and_(Shift.org_id == member.org_id, Shift.staff_id == s.staff_id, Shift.start_at == new_start)
                )
            )
            if exists:
                skipped += 1
                continue
            db.add(Shift(
                id=uuid.uuid4(),
                org_id=member.org_id,
                staff_id=s.staff_id,
                start_at=new_start,
                end_at=new_end,
                hourly_rate=s.hourly_rate,
                notes=s.notes,
                color=s.color,
                roster_week=new_week_iso,
            ))
            created += 1
        await db.commit()
        return {"created": created, "skipped": skipped, "week_start": str(week_start)}
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"copy_last_week failed: {exc}", extra={"org_id": str(member.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/roster/publish")
async def publish_roster(
    week_start: date = Query(...),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    try:
        existing = await db.scalar(
            select(RosterPublication).where(
                and_(
                    RosterPublication.org_id == member.org_id,
                    RosterPublication.week_start == week_start,
                )
            )
        )
        if existing:
            return {"week_start": str(week_start), "published_at": existing.published_at.isoformat(), "already_published": True}

        pub = RosterPublication(
            id=uuid.uuid4(),
            org_id=member.org_id,
            week_start=week_start,
            published_by=user.get("user_id"),
        )
        db.add(pub)
        await db.commit()
        await db.refresh(pub)

        # Push notifications — fire and forget
        async def _push_publish():
            try:
                from app.models.notifications import DeviceToken
                from app.services.push import send_expo_push
                tokens = list((await db.scalars(
                    select(DeviceToken.token).where(DeviceToken.org_id == member.org_id)
                )).all())
                if tokens:
                    await send_expo_push(
                        tokens,
                        title="Roster published",
                        body=f"Your schedule for the week of {week_start} is now available.",
                        db=db,
                    )
            except Exception as push_exc:
                log.warning(f"publish push failed: {push_exc}")

        asyncio.create_task(_push_publish())

        return {"week_start": str(week_start), "published_at": pub.published_at.isoformat(), "already_published": False}
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"publish_roster failed: {exc}", extra={"org_id": str(member.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Shift Swap endpoints ──────────────────────────────────────────────────────

class SwapCreate(BaseModel):
    requester_shift_id: uuid.UUID
    requester_staff_id: uuid.UUID
    target_staff_id: uuid.UUID
    target_shift_id: Optional[uuid.UUID] = None
    requester_note: Optional[str] = None


class SwapReview(BaseModel):
    manager_notes: Optional[str] = None


def _swap_row(r: ShiftSwapRequest) -> dict:
    return {c.name: str(getattr(r, c.name)) if getattr(r, c.name) is not None else None for c in r.__table__.columns}


@router.get("/swaps")
async def list_swaps(
    status: Optional[str] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _user, member = ctx
    try:
        q = select(ShiftSwapRequest).where(ShiftSwapRequest.org_id == member.org_id)
        if status:
            q = q.where(ShiftSwapRequest.status == status)
        rows = (await db.scalars(q.order_by(ShiftSwapRequest.created_at.desc()))).all()
        return [_swap_row(r) for r in rows]
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"list_swaps failed: {exc}", extra={"org_id": str(member.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/swaps", status_code=201)
async def create_swap(
    body: SwapCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _user, member = ctx
    try:
        # Validate the requester shift belongs to this org
        shift = await db.scalar(
            select(Shift).where(and_(Shift.id == body.requester_shift_id, Shift.org_id == member.org_id))
        )
        if not shift:
            raise HTTPException(status_code=404, detail="Requester shift not found")
        row = ShiftSwapRequest(
            id=uuid.uuid4(),
            org_id=member.org_id,
            requester_shift_id=body.requester_shift_id,
            requester_staff_id=body.requester_staff_id,
            target_staff_id=body.target_staff_id,
            target_shift_id=body.target_shift_id,
            requester_note=body.requester_note,
            status="pending",
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _swap_row(row)
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"create_swap failed: {exc}", extra={"org_id": str(member.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/swaps/{swap_id}/approve")
async def approve_swap(
    swap_id: uuid.UUID,
    body: SwapReview = SwapReview(),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _user, member = ctx
    try:
        row = await db.scalar(
            select(ShiftSwapRequest).where(
                and_(ShiftSwapRequest.id == swap_id, ShiftSwapRequest.org_id == member.org_id)
            )
        )
        if not row:
            raise HTTPException(status_code=404, detail="Swap request not found")
        if row.status != "pending":
            raise HTTPException(status_code=422, detail="Only pending swap requests can be approved")

        # Swap the staff_id on both shifts
        req_shift = await db.get(Shift, row.requester_shift_id)
        if req_shift:
            req_shift.staff_id = row.target_staff_id
        if row.target_shift_id:
            tgt_shift = await db.get(Shift, row.target_shift_id)
            if tgt_shift:
                tgt_shift.staff_id = row.requester_staff_id

        row.status = "approved"
        row.manager_notes = body.manager_notes
        row.resolved_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(row)
        return _swap_row(row)
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"approve_swap failed: {exc}", extra={"org_id": str(member.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/swaps/{swap_id}/reject")
async def reject_swap(
    swap_id: uuid.UUID,
    body: SwapReview = SwapReview(),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _user, member = ctx
    try:
        row = await db.scalar(
            select(ShiftSwapRequest).where(
                and_(ShiftSwapRequest.id == swap_id, ShiftSwapRequest.org_id == member.org_id)
            )
        )
        if not row:
            raise HTTPException(status_code=404, detail="Swap request not found")
        if row.status != "pending":
            raise HTTPException(status_code=422, detail="Only pending swap requests can be rejected")
        row.status = "rejected"
        row.manager_notes = body.manager_notes
        row.resolved_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(row)
        return _swap_row(row)
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"reject_swap failed: {exc}", extra={"org_id": str(member.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
