"""Timesheet approval router (Feature 16).

Workflow: draft → submitted → approved | rejected

Key endpoints:
  POST /api/hr/timesheets/generate     — build timesheets from punches for a week
  GET  /api/hr/timesheets              — list with filters
  GET  /api/hr/timesheets/{id}         — detail + lines
  POST /api/hr/timesheets/{id}/submit  — staff/manager marks submitted
  POST /api/hr/timesheets/{id}/approve — manager approves (locks)
  POST /api/hr/timesheets/{id}/reject  — manager rejects with comment
  PATCH /api/hr/timesheets/{id}/lines/{line_id} — adjust a line
  GET  /api/hr/timesheets/export       — payroll CSV of approved timesheets
"""
from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.bookings import Staff
from app.models.employee_contracts import EmployeeContract
from app.models.shift import Shift, ShiftPunch
from app.models.timesheet import Timesheet, TimesheetLine

log = logging.getLogger(__name__)
router = APIRouter()

_DEFAULT_WEEKLY_HOURS = Decimal("40")


# ── helpers ──────────────────────────────────────────────────────────────────

def _row(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def _effective_hours(line: TimesheetLine) -> Decimal:
    """Return adjusted hours if set, otherwise raw."""
    return line.hours_adjusted if line.hours_adjusted is not None else line.hours_raw


def _week_monday(d: date) -> date:
    """Return the Monday of the ISO week containing d."""
    return d - timedelta(days=d.weekday())


async def _recompute_totals(ts: Timesheet, lines: list[TimesheetLine], db: AsyncSession,
                            contracted_hours: Decimal) -> None:
    """Recompute denormalised totals on the Timesheet row."""
    total = sum(_effective_hours(ln) for ln in lines)
    overtime = max(Decimal("0"), total - contracted_hours)
    regular = total - overtime

    # cost: use hourly rate from the most recent Shift for this staff/week if available
    ts.total_hours = total
    ts.regular_hours = regular
    ts.overtime_hours = overtime

    # cost computation — look up hourly_rate from any shift in the week
    week_end = ts.week_start + timedelta(days=6)
    shift_row = (await db.execute(
        select(Shift).where(
            and_(
                Shift.org_id == ts.org_id,
                Shift.staff_id == ts.staff_id,
                Shift.start_at >= datetime.combine(ts.week_start, datetime.min.time()).replace(tzinfo=timezone.utc),
                Shift.start_at <= datetime.combine(week_end, datetime.max.time()).replace(tzinfo=timezone.utc),
                Shift.hourly_rate.isnot(None),
            )
        ).limit(1)
    )).scalar_one_or_none()

    if shift_row and shift_row.hourly_rate:
        ts.total_cost = total * shift_row.hourly_rate
    else:
        ts.total_cost = None

    ts.updated_at = datetime.now(timezone.utc)


async def _contracted_hours(org_id: uuid.UUID, staff_id: uuid.UUID, db: AsyncSession) -> Decimal:
    """Return weekly contracted hours for a staff member, defaulting to 40."""
    contract = (await db.execute(
        select(EmployeeContract).where(
            and_(
                EmployeeContract.org_id == org_id,
                EmployeeContract.staff_id == staff_id,
            )
        ).order_by(EmployeeContract.start_date.desc()).limit(1)
    )).scalar_one_or_none()
    if contract and contract.hours_per_week:
        return Decimal(str(contract.hours_per_week))
    return _DEFAULT_WEEKLY_HOURS


# ── schemas ───────────────────────────────────────────────────────────────────

class LineAdjust(BaseModel):
    hours_adjusted: Decimal
    adjustment_reason: Optional[str] = None


class ActionBody(BaseModel):
    comment: Optional[str] = None


# ── routes ────────────────────────────────────────────────────────────────────

# IMPORTANT: static paths before /{id} to avoid capture

@router.post("/api/hr/timesheets/generate", status_code=201)
async def generate_timesheets(
    week_start: date = Query(..., description="Monday of the week to generate, e.g. 2026-04-27"),
    staff_id: Optional[uuid.UUID] = Query(None, description="Generate for one staff only"),
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Build/refresh timesheets from shift punches. Safe to re-run (idempotent on draft/submitted)."""
    user, member = auth
    org_id = member.org_id
    try:
        week_monday = _week_monday(week_start)
        week_end = week_monday + timedelta(days=6)

        # Find all punches in the week for this org (optionally one staff)
        q = select(ShiftPunch).where(
            and_(
                ShiftPunch.org_id == org_id,
                ShiftPunch.clock_in_at >= datetime.combine(week_monday, datetime.min.time()).replace(tzinfo=timezone.utc),
                ShiftPunch.clock_in_at <= datetime.combine(week_end, datetime.max.time()).replace(tzinfo=timezone.utc),
            )
        )
        if staff_id:
            q = q.where(ShiftPunch.staff_id == staff_id)
        punches = (await db.execute(q)).scalars().all()

        # Group by staff
        by_staff: dict[uuid.UUID, list[ShiftPunch]] = {}
        for p in punches:
            by_staff.setdefault(p.staff_id, []).append(p)

        created = []
        for sid, staff_punches in by_staff.items():
            # Find or create timesheet
            ts = (await db.execute(
                select(Timesheet).where(
                    and_(
                        Timesheet.org_id == org_id,
                        Timesheet.staff_id == sid,
                        Timesheet.week_start == week_monday,
                    )
                )
            )).scalar_one_or_none()

            if ts and ts.status == "approved":
                # Don't overwrite approved timesheets
                continue

            if not ts:
                ts = Timesheet(
                    id=uuid.uuid4(),
                    org_id=org_id,
                    staff_id=sid,
                    week_start=week_monday,
                    status="draft",
                )
                db.add(ts)
                await db.flush()

            # Remove old lines (safe to regenerate)
            old_lines = (await db.execute(
                select(TimesheetLine).where(TimesheetLine.timesheet_id == ts.id)
            )).scalars().all()
            for ln in old_lines:
                await db.delete(ln)
            await db.flush()

            # Create new lines from punches
            new_lines: list[TimesheetLine] = []
            for punch in sorted(staff_punches, key=lambda p: p.clock_in_at):
                if punch.clock_out_at:
                    raw_h = Decimal(str(
                        round((punch.clock_out_at - punch.clock_in_at).total_seconds() / 3600, 2)
                    ))
                else:
                    raw_h = Decimal("0")

                ln = TimesheetLine(
                    id=uuid.uuid4(),
                    timesheet_id=ts.id,
                    punch_id=punch.id,
                    work_date=punch.clock_in_at.date(),
                    clock_in_at=punch.clock_in_at,
                    clock_out_at=punch.clock_out_at,
                    hours_raw=raw_h,
                )
                db.add(ln)
                new_lines.append(ln)

            contracted = await _contracted_hours(org_id, sid, db)
            await _recompute_totals(ts, new_lines, db, contracted)
            created.append(_row(ts))

        await db.commit()
        return {"generated": len(created), "week_start": week_monday.isoformat(), "timesheets": created}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"generate_timesheets failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/hr/timesheets/export")
async def export_timesheets(
    week_start: Optional[date] = Query(None),
    status: str = Query("approved"),
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """CSV export of timesheets for payroll. Defaults to approved timesheets."""
    user, member = auth
    org_id = member.org_id
    try:
        q = select(Timesheet, Staff).join(Staff, Staff.id == Timesheet.staff_id).where(
            and_(Timesheet.org_id == org_id, Timesheet.status == status)
        )
        if week_start:
            q = q.where(Timesheet.week_start == _week_monday(week_start))
        q = q.order_by(Staff.name, Timesheet.week_start)
        rows = (await db.execute(q)).all()

        buf = io.StringIO()
        buf.write("\ufeff")  # utf-8-sig BOM for Excel
        writer = csv.writer(buf)
        writer.writerow([
            "Staff Name", "Week Start", "Status",
            "Total Hours", "Regular Hours", "Overtime Hours",
            "Total Cost", "Currency",
        ])
        for ts, staff in rows:
            writer.writerow([
                staff.name,
                ts.week_start.isoformat(),
                ts.status,
                float(ts.total_hours),
                float(ts.regular_hours),
                float(ts.overtime_hours),
                float(ts.total_cost) if ts.total_cost else "",
                "SEK",
            ])

        buf.seek(0)
        filename = f"timesheets_{week_start or 'all'}_{status}.csv"
        return StreamingResponse(
            iter([buf.read()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"export_timesheets failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/hr/timesheets")
async def list_timesheets(
    week_start: Optional[date] = Query(None),
    staff_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = 100,
    offset: int = 0,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        q = (
            select(Timesheet, Staff)
            .join(Staff, Staff.id == Timesheet.staff_id)
            .where(Timesheet.org_id == org_id)
        )
        if week_start:
            q = q.where(Timesheet.week_start == _week_monday(week_start))
        if staff_id:
            q = q.where(Timesheet.staff_id == staff_id)
        if status:
            q = q.where(Timesheet.status == status)
        q = q.order_by(Timesheet.week_start.desc(), Staff.name).limit(limit).offset(offset)
        rows = (await db.execute(q)).all()
        return [
            {**_row(ts), "staff_name": staff.name}
            for ts, staff in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_timesheets failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/hr/timesheets/{timesheet_id}")
async def get_timesheet(
    timesheet_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        ts = (await db.execute(
            select(Timesheet).where(
                and_(Timesheet.org_id == org_id, Timesheet.id == timesheet_id)
            )
        )).scalar_one_or_none()
        if not ts:
            raise HTTPException(status_code=404, detail="Timesheet not found")

        lines = (await db.execute(
            select(TimesheetLine).where(TimesheetLine.timesheet_id == ts.id)
            .order_by(TimesheetLine.work_date, TimesheetLine.clock_in_at)
        )).scalars().all()

        staff = (await db.execute(
            select(Staff).where(Staff.id == ts.staff_id)
        )).scalar_one_or_none()

        return {
            **_row(ts),
            "staff_name": staff.name if staff else None,
            "lines": [_row(ln) for ln in lines],
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"get_timesheet failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/timesheets/{timesheet_id}/submit")
async def submit_timesheet(
    timesheet_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Staff or manager marks a draft timesheet as submitted for review."""
    user, member = auth
    org_id = member.org_id
    try:
        ts = (await db.execute(
            select(Timesheet).where(
                and_(Timesheet.org_id == org_id, Timesheet.id == timesheet_id)
            )
        )).scalar_one_or_none()
        if not ts:
            raise HTTPException(status_code=404, detail="Timesheet not found")
        if ts.status not in ("draft", "rejected"):
            raise HTTPException(status_code=409, detail=f"Cannot submit a timesheet in '{ts.status}' status")

        ts.status = "submitted"
        ts.submitted_at = datetime.now(timezone.utc)
        ts.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(ts)
        return _row(ts)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"submit_timesheet failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/timesheets/{timesheet_id}/approve")
async def approve_timesheet(
    timesheet_id: uuid.UUID,
    body: ActionBody = ActionBody(),
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Manager approves a submitted timesheet. Locks it from further edits."""
    user, member = auth
    org_id = member.org_id
    try:
        ts = (await db.execute(
            select(Timesheet).where(
                and_(Timesheet.org_id == org_id, Timesheet.id == timesheet_id)
            )
        )).scalar_one_or_none()
        if not ts:
            raise HTTPException(status_code=404, detail="Timesheet not found")
        if ts.status != "submitted":
            raise HTTPException(status_code=409, detail=f"Cannot approve a timesheet in '{ts.status}' status")

        ts.status = "approved"
        ts.approved_at = datetime.now(timezone.utc)
        ts.approved_by = uuid.UUID(user["id"]) if user.get("id") else None
        if body.comment:
            ts.manager_comment = body.comment
        ts.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(ts)
        return _row(ts)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"approve_timesheet failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/timesheets/{timesheet_id}/reject")
async def reject_timesheet(
    timesheet_id: uuid.UUID,
    body: ActionBody,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Manager rejects a submitted timesheet with a comment."""
    user, member = auth
    org_id = member.org_id
    try:
        ts = (await db.execute(
            select(Timesheet).where(
                and_(Timesheet.org_id == org_id, Timesheet.id == timesheet_id)
            )
        )).scalar_one_or_none()
        if not ts:
            raise HTTPException(status_code=404, detail="Timesheet not found")
        if ts.status != "submitted":
            raise HTTPException(status_code=409, detail=f"Cannot reject a timesheet in '{ts.status}' status")

        ts.status = "rejected"
        ts.rejected_at = datetime.now(timezone.utc)
        ts.manager_comment = body.comment
        ts.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(ts)
        return _row(ts)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"reject_timesheet failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/timesheets/{timesheet_id}/unlock")
async def unlock_timesheet(
    timesheet_id: uuid.UUID,
    body: ActionBody,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Manager override: unlock an approved timesheet for corrections."""
    user, member = auth
    org_id = member.org_id
    try:
        ts = (await db.execute(
            select(Timesheet).where(
                and_(Timesheet.org_id == org_id, Timesheet.id == timesheet_id)
            )
        )).scalar_one_or_none()
        if not ts:
            raise HTTPException(status_code=404, detail="Timesheet not found")
        if ts.status != "approved":
            raise HTTPException(status_code=409, detail="Only approved timesheets can be unlocked")

        ts.status = "submitted"
        ts.manager_comment = body.comment
        ts.approved_at = None
        ts.approved_by = None
        ts.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(ts)
        return _row(ts)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"unlock_timesheet failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/hr/timesheets/{timesheet_id}/lines/{line_id}")
async def adjust_line(
    timesheet_id: uuid.UUID,
    line_id: uuid.UUID,
    body: LineAdjust,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Manager adjusts hours on one line. Recomputes timesheet totals."""
    user, member = auth
    org_id = member.org_id
    try:
        ts = (await db.execute(
            select(Timesheet).where(
                and_(Timesheet.org_id == org_id, Timesheet.id == timesheet_id)
            )
        )).scalar_one_or_none()
        if not ts:
            raise HTTPException(status_code=404, detail="Timesheet not found")
        if ts.status == "approved":
            raise HTTPException(status_code=409, detail="Timesheet is locked. Unlock it first.")

        ln = (await db.execute(
            select(TimesheetLine).where(
                and_(TimesheetLine.timesheet_id == timesheet_id, TimesheetLine.id == line_id)
            )
        )).scalar_one_or_none()
        if not ln:
            raise HTTPException(status_code=404, detail="Line not found")

        ln.hours_adjusted = body.hours_adjusted
        ln.adjustment_reason = body.adjustment_reason

        # Recompute all lines for this timesheet
        all_lines = (await db.execute(
            select(TimesheetLine).where(TimesheetLine.timesheet_id == ts.id)
        )).scalars().all()
        contracted = await _contracted_hours(org_id, ts.staff_id, db)
        await _recompute_totals(ts, all_lines, db, contracted)

        await db.commit()
        await db.refresh(ts)
        await db.refresh(ln)
        return {"timesheet": _row(ts), "line": _row(ln)}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"adjust_line failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
