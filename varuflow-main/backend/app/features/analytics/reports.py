"""Reports router — manager dashboard, staff productivity, attendance."""
import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.features.invoicing.models import Invoice
from app.features.bookings.models import Appointment, Staff
from app.features.hr.shift import Shift, ShiftPunch
from app.features.inventory.models import PurchaseOrder
from app.features.purchases.models import PurchaseRequest
from app.features.expenses.petty_cash_models import PettyCashTransaction
from app.features.projects.models import ProjectTimeEntry

logger = logging.getLogger(__name__)
router = APIRouter(tags=["reports"], dependencies=[Depends(require_module("analytics"))])


@router.get("/api/reports/manager-dashboard")
async def manager_dashboard(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Scoped dashboard for managers — pending approvals, team metrics."""
    try:
        org_id = member["org_id"]
        role = member.get("role", "MEMBER")
        if role not in ("OWNER", "ADMIN"):
            raise HTTPException(status_code=403, detail="Manager access required")

        # Pending purchase requests
        pending_pr = (await db.execute(
            select(func.count()).select_from(PurchaseRequest)
            .where(PurchaseRequest.org_id == org_id, PurchaseRequest.status == "pending")
        )).scalar()

        # Pending timesheet approvals
        pending_ts = (await db.execute(
            select(func.count()).select_from(ProjectTimeEntry)
            .where(ProjectTimeEntry.org_id == org_id, ProjectTimeEntry.approval_status == "pending")
        )).scalar()

        # This month invoices total
        month_start = date.today().replace(day=1)
        invoices_total = (await db.execute(
            select(func.coalesce(func.sum(Invoice.total_sek), 0))
            .where(Invoice.org_id == org_id, Invoice.issue_date >= month_start)
        )).scalar()

        # Petty cash balance
        deposits = (await db.execute(
            select(func.coalesce(func.sum(PettyCashTransaction.amount), 0))
            .where(PettyCashTransaction.org_id == org_id, PettyCashTransaction.txn_type == "deposit")
        )).scalar()
        withdrawals = (await db.execute(
            select(func.coalesce(func.sum(PettyCashTransaction.amount), 0))
            .where(PettyCashTransaction.org_id == org_id, PettyCashTransaction.txn_type == "withdrawal")
        )).scalar()

        return {
            "pending_purchase_requests": pending_pr,
            "pending_timesheet_approvals": pending_ts,
            "invoices_total_this_month": float(invoices_total),
            "petty_cash_balance": float(deposits) - float(withdrawals),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"manager_dashboard failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/reports/staff-productivity")
async def staff_productivity(
    from_date: date | None = None,
    to_date: date | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Invoices raised and appointments completed per staff member."""
    try:
        org_id = member["org_id"]
        role = member.get("role", "MEMBER")
        if role not in ("OWNER", "ADMIN"):
            raise HTTPException(status_code=403, detail="Manager access required")

        if not from_date:
            from_date = date.today().replace(day=1)
        if not to_date:
            to_date = date.today()

        # Staff list
        staff_rows = (await db.execute(
            select(Staff).where(Staff.org_id == org_id)
        )).scalars().all()

        results = []
        for s in staff_rows:
            # Invoices created by this staff
            inv_count = (await db.execute(
                select(func.count()).select_from(Invoice)
                .where(Invoice.org_id == org_id, Invoice.created_by_staff_id == s.id, Invoice.issue_date >= from_date, Invoice.issue_date <= to_date)
            )).scalar()

            # Appointments completed
            appt_count = (await db.execute(
                select(func.count()).select_from(Appointment)
                .where(Appointment.org_id == org_id, Appointment.staff_id == s.id, Appointment.status == "completed", Appointment.start_time >= datetime.combine(from_date, datetime.min.time()), Appointment.start_time <= datetime.combine(to_date, datetime.max.time()))
            )).scalar()

            # Billable hours
            hours = (await db.execute(
                select(func.coalesce(func.sum(ProjectTimeEntry.hours), 0))
                .where(ProjectTimeEntry.org_id == org_id, ProjectTimeEntry.staff_id == s.id, ProjectTimeEntry.billable == True, ProjectTimeEntry.entry_date >= from_date, ProjectTimeEntry.entry_date <= to_date)
            )).scalar()

            results.append({
                "staff_id": str(s.id),
                "staff_name": s.display_name if hasattr(s, 'display_name') else f"{s.first_name} {s.last_name}" if hasattr(s, 'first_name') else str(s.id),
                "invoices_raised": inv_count,
                "appointments_completed": appt_count,
                "billable_hours": float(hours),
            })

        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"staff_productivity failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/reports/attendance")
async def attendance_report(
    week_start: date | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Attendance: scheduled shifts vs actual clock-in."""
    try:
        org_id = member["org_id"]
        role = member.get("role", "MEMBER")
        if role not in ("OWNER", "ADMIN"):
            raise HTTPException(status_code=403, detail="Manager access required")

        if not week_start:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        week_start_dt = datetime.combine(week_start, datetime.min.time()).replace(tzinfo=timezone.utc)
        week_end_dt = datetime.combine(week_end + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc)

        staff_rows = (await db.execute(select(Staff).where(Staff.org_id == org_id))).scalars().all()

        # Scheduled shifts per staff for the week
        scheduled_rows = (await db.execute(
            select(Shift.staff_id, func.count().label("cnt"))
            .where(
                Shift.org_id == org_id,
                Shift.start_at >= week_start_dt,
                Shift.start_at < week_end_dt,
            )
            .group_by(Shift.staff_id)
        )).all()
        scheduled_by_staff = {row.staff_id: row.cnt for row in scheduled_rows}

        # Attended (punched in) per staff for the week
        attended_rows = (await db.execute(
            select(ShiftPunch.staff_id, func.count().label("cnt"))
            .where(
                ShiftPunch.org_id == org_id,
                ShiftPunch.clock_in_at >= week_start_dt,
                ShiftPunch.clock_in_at < week_end_dt,
            )
            .group_by(ShiftPunch.staff_id)
        )).all()
        attended_by_staff = {row.staff_id: row.cnt for row in attended_rows}

        # Late arrivals: clock_in_at after shift start_at
        late_rows = (await db.execute(
            select(ShiftPunch.staff_id, func.count().label("cnt"))
            .join(Shift, ShiftPunch.shift_id == Shift.id)
            .where(
                ShiftPunch.org_id == org_id,
                ShiftPunch.clock_in_at >= week_start_dt,
                ShiftPunch.clock_in_at < week_end_dt,
                ShiftPunch.clock_in_at > Shift.start_at,
            )
            .group_by(ShiftPunch.staff_id)
        )).all()
        late_by_staff = {row.staff_id: row.cnt for row in late_rows}

        results = []
        for s in staff_rows:
            scheduled = scheduled_by_staff.get(s.id, 0)
            attended = attended_by_staff.get(s.id, 0)
            results.append({
                "staff_id": str(s.id),
                "staff_name": s.name,
                "scheduled_shifts": scheduled,
                "attended": attended,
                "missed": max(0, scheduled - attended),
                "late": late_by_staff.get(s.id, 0),
            })

        return {"week_start": week_start.isoformat(), "week_end": week_end.isoformat(), "staff": results}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"attendance_report failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")
