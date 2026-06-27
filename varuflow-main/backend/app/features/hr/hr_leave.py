"""HR Leave router: leave requests, approval, rejection, balance, calendar, export, entitlements."""
from __future__ import annotations

import asyncio
import csv
import io
import logging
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module, require_role
from app.features.bookings.models import Staff
from .leave_entitlement import LeaveEntitlement, PublicHoliday
from .leave_requests import LeaveRequest
from app.features.auth.organization import OrgRole

# Approving / rejecting someone else's leave is a manager action. Requesting and
# viewing one's OWN leave stays open to any HR-module member.
_MANAGER_ONLY = [Depends(require_role(OrgRole.ADMIN))]
from .staff_availability import StaffAvailabilityOverride

log = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_module("hr"))])

VALID_LEAVE_TYPES = {"annual", "sick", "parental", "unpaid", "public_holiday", "other"}
VALID_STATUSES = {"pending", "approved", "rejected", "cancelled"}

# ── Public holiday seed data ──────────────────────────────────────────────────

_HOLIDAYS_2026: dict[str, list[tuple[str, str]]] = {
    "SE": [
        ("2026-01-01", "Nyårsdagen"),
        ("2026-01-06", "Trettondedag jul"),
        ("2026-04-03", "Långfredagen"),
        ("2026-04-05", "Påskdagen"),
        ("2026-04-06", "Annandag påsk"),
        ("2026-05-01", "Första maj"),
        ("2026-05-14", "Kristi himmelsfärdsdag"),
        ("2026-05-24", "Pingstdagen"),
        ("2026-06-06", "Sveriges nationaldag"),
        ("2026-06-20", "Midsommarafton"),
        ("2026-06-21", "Midsommardagen"),
        ("2026-11-07", "Alla helgons dag"),
        ("2026-12-24", "Julafton"),
        ("2026-12-25", "Juldagen"),
        ("2026-12-26", "Annandag jul"),
        ("2026-12-31", "Nyårsafton"),
    ],
    "AE": [
        ("2026-01-01", "New Year's Day"),
        ("2026-03-29", "Eid Al Fitr"),
        ("2026-03-30", "Eid Al Fitr"),
        ("2026-03-31", "Eid Al Fitr"),
        ("2026-06-06", "Arafat Day"),
        ("2026-06-07", "Eid Al Adha"),
        ("2026-06-08", "Eid Al Adha"),
        ("2026-06-09", "Eid Al Adha"),
        ("2026-06-26", "Islamic New Year"),
        ("2026-09-04", "Prophet's Birthday"),
        ("2026-12-02", "UAE National Day"),
        ("2026-12-03", "UAE National Day"),
    ],
    "SA": [
        ("2026-02-22", "Saudi Founding Day"),
        ("2026-03-29", "Eid Al Fitr"),
        ("2026-03-30", "Eid Al Fitr"),
        ("2026-03-31", "Eid Al Fitr"),
        ("2026-06-05", "Arafat Day"),
        ("2026-06-06", "Eid Al Adha"),
        ("2026-06-07", "Eid Al Adha"),
        ("2026-06-08", "Eid Al Adha"),
        ("2026-09-23", "Saudi National Day"),
    ],
    "MA": [
        ("2026-01-01", "Nouvel An"),
        ("2026-01-11", "Manifeste de l'Indépendance"),
        ("2026-03-29", "Aïd Al Fitr"),
        ("2026-03-30", "Aïd Al Fitr"),
        ("2026-05-01", "Fête du Travail"),
        ("2026-06-06", "Aïd Al Adha"),
        ("2026-06-07", "Aïd Al Adha"),
        ("2026-07-30", "Fête du Trône"),
        ("2026-08-14", "Journée de l'Oued Ed-Dahab"),
        ("2026-08-20", "Fête de la Révolution"),
        ("2026-08-21", "Fête de la Jeunesse"),
        ("2026-11-06", "Marche Verte"),
        ("2026-11-18", "Fête de l'Indépendance"),
    ],
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row(obj: Any) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


async def _notify(to_email: str, subject: str, body_html: str) -> None:
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key or not to_email:
        return
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "from": "Varuflow HR <noreply@varuflow.com>",
                    "to": [to_email],
                    "subject": subject,
                    "html": body_html,
                },
            )
    except Exception as exc:
        log.warning(f"leave notify failed: {exc}")


def _business_days(start: date, end: date, holiday_dates: set[date], half_day: bool = False) -> Decimal:
    """Count weekdays between start and end (inclusive), excluding holiday_dates."""
    total = 0
    d = start
    while d <= end:
        if d.weekday() < 5 and d not in holiday_dates:
            total += 1
        d += timedelta(days=1)
    days = Decimal(str(total))
    return days / 2 if half_day else days


async def _get_holiday_dates(org_id: uuid.UUID, year: int, db: AsyncSession) -> set[date]:
    rows = (await db.execute(
        select(PublicHoliday).where(
            and_(PublicHoliday.org_id == org_id, PublicHoliday.year == year)
        )
    )).scalars().all()
    return {r.holiday_date for r in rows}


# ── Schemas ───────────────────────────────────────────────────────────────────

class LeaveRequestCreate(BaseModel):
    staff_id: uuid.UUID
    leave_type: str
    start_date: date
    end_date: date
    half_day: bool = False
    reason: Optional[str] = None


class LeaveRequestUpdate(BaseModel):
    leave_type: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    half_day: Optional[bool] = None
    reason: Optional[str] = None


class ReviewBody(BaseModel):
    reviewer_note: Optional[str] = None


class RejectBody(BaseModel):
    rejection_reason: Optional[str] = None
    reviewer_note: Optional[str] = None


class EntitlementUpsert(BaseModel):
    staff_id: uuid.UUID
    leave_type: str
    year: int
    days_allocated: Decimal
    carry_over_days: Decimal = Decimal("0")
    carry_over_cap: Optional[Decimal] = None


class HolidaySeedBody(BaseModel):
    country_code: str
    year: int = 2026


# ── Balance ───────────────────────────────────────────────────────────────────

@router.get("/api/hr/leave/balance/{staff_id}")
async def get_leave_balance(
    staff_id: uuid.UUID,
    year: int = Query(default=None),
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    if year is None:
        year = date.today().year
    try:
        entitlements = (await db.execute(
            select(LeaveEntitlement).where(
                and_(
                    LeaveEntitlement.org_id == org_id,
                    LeaveEntitlement.staff_id == staff_id,
                    LeaveEntitlement.year == year,
                )
            )
        )).scalars().all()

        holiday_dates = await _get_holiday_dates(org_id, year, db)

        approved_requests = (await db.execute(
            select(LeaveRequest).where(
                and_(
                    LeaveRequest.org_id == org_id,
                    LeaveRequest.staff_id == staff_id,
                    LeaveRequest.status == "approved",
                )
            )
        )).scalars().all()

        # Group used days by leave type (only requests in the given year)
        used_by_type: dict[str, Decimal] = {}
        pending_by_type: dict[str, Decimal] = {}
        for req in approved_requests:
            if req.start_date.year == year or req.end_date.year == year:
                bd = _business_days(req.start_date, req.end_date, holiday_dates, req.half_day)
                used_by_type[req.leave_type] = used_by_type.get(req.leave_type, Decimal("0")) + bd

        pending_requests = (await db.execute(
            select(LeaveRequest).where(
                and_(
                    LeaveRequest.org_id == org_id,
                    LeaveRequest.staff_id == staff_id,
                    LeaveRequest.status == "pending",
                )
            )
        )).scalars().all()
        for req in pending_requests:
            if req.start_date.year == year or req.end_date.year == year:
                bd = _business_days(req.start_date, req.end_date, holiday_dates, req.half_day)
                pending_by_type[req.leave_type] = pending_by_type.get(req.leave_type, Decimal("0")) + bd

        result = []
        ent_map = {e.leave_type: e for e in entitlements}
        all_types = set(ent_map.keys()) | set(used_by_type.keys()) | set(pending_by_type.keys())
        for lt in sorted(all_types):
            ent = ent_map.get(lt)
            allocated = (ent.days_allocated + ent.carry_over_days) if ent else Decimal("0")
            used = used_by_type.get(lt, Decimal("0"))
            pending = pending_by_type.get(lt, Decimal("0"))
            result.append({
                "leave_type": lt,
                "days_allocated": float(allocated),
                "days_used": float(used),
                "days_pending": float(pending),
                "days_remaining": float(max(Decimal("0"), allocated - used)),
                "carry_over_cap": float(ent.carry_over_cap) if ent and ent.carry_over_cap else None,
            })
        return {"staff_id": str(staff_id), "year": year, "balances": result}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"get_leave_balance failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Calendar ──────────────────────────────────────────────────────────────────

@router.get("/api/hr/leave/calendar")
async def leave_calendar(
    week_start: date = Query(..., description="Monday of the week (YYYY-MM-DD)"),
    country_code: str = Query(default="SE"),
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        week_end = week_start + timedelta(days=6)
        leaves = (await db.execute(
            select(LeaveRequest).where(
                and_(
                    LeaveRequest.org_id == org_id,
                    LeaveRequest.status.in_(["approved", "pending"]),
                    LeaveRequest.start_date <= week_end,
                    LeaveRequest.end_date >= week_start,
                )
            )
        )).scalars().all()

        # Fetch staff names
        staff_ids = {r.staff_id for r in leaves}
        staff_map: dict[str, str] = {}
        if staff_ids:
            staff_rows = (await db.execute(
                select(Staff).where(Staff.id.in_(staff_ids))
            )).scalars().all()
            staff_map = {str(s.id): s.name for s in staff_rows}

        holidays = (await db.execute(
            select(PublicHoliday).where(
                and_(
                    PublicHoliday.org_id == org_id,
                    PublicHoliday.country_code == country_code,
                    PublicHoliday.holiday_date >= week_start,
                    PublicHoliday.holiday_date <= week_end,
                )
            )
        )).scalars().all()

        return {
            "week_start": str(week_start),
            "week_end": str(week_end),
            "leaves": [
                {
                    **_row(r),
                    "staff_name": staff_map.get(str(r.staff_id), "Unknown"),
                }
                for r in leaves
            ],
            "public_holidays": [
                {"date": str(h.holiday_date), "name": h.name, "country_code": h.country_code}
                for h in holidays
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"leave_calendar failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Export (CSV) ──────────────────────────────────────────────────────────────

@router.get("/api/hr/leave/export")
async def export_leave(
    from_date: date = Query(...),
    to_date: date = Query(...),
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        rows = (await db.execute(
            select(LeaveRequest).where(
                and_(
                    LeaveRequest.org_id == org_id,
                    LeaveRequest.status == "approved",
                    LeaveRequest.start_date <= to_date,
                    LeaveRequest.end_date >= from_date,
                )
            ).order_by(LeaveRequest.start_date)
        )).scalars().all()

        holiday_dates = await _get_holiday_dates(org_id, from_date.year, db)

        staff_ids = {r.staff_id for r in rows}
        staff_map: dict[str, str] = {}
        if staff_ids:
            staff_rows = (await db.execute(
                select(Staff).where(Staff.id.in_(staff_ids))
            )).scalars().all()
            staff_map = {str(s.id): s.name for s in staff_rows}

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["staff_id", "staff_name", "leave_type", "start_date", "end_date", "half_day", "days_taken", "status", "reason"])
        for r in rows:
            bd = _business_days(r.start_date, r.end_date, holiday_dates, r.half_day)
            writer.writerow([
                str(r.staff_id),
                staff_map.get(str(r.staff_id), ""),
                r.leave_type,
                str(r.start_date),
                str(r.end_date),
                r.half_day,
                float(bd),
                r.status,
                r.reason or "",
            ])
        output.seek(0)
        filename = f"leave_export_{from_date}_{to_date}.csv"
        return StreamingResponse(
            io.BytesIO(output.read().encode("utf-8-sig")),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"export_leave failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Public Holidays ───────────────────────────────────────────────────────────

@router.get("/api/hr/leave/holidays")
async def list_holidays(
    country_code: str = Query(default="SE"),
    year: int = Query(default=None),
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    if year is None:
        year = date.today().year
    try:
        q = select(PublicHoliday).where(
            and_(PublicHoliday.org_id == org_id, PublicHoliday.country_code == country_code, PublicHoliday.year == year)
        ).order_by(PublicHoliday.holiday_date)
        rows = (await db.execute(q)).scalars().all()
        return [_row(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_holidays failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/leave/holidays/seed", status_code=201)
async def seed_holidays(
    body: HolidaySeedBody,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    cc = body.country_code.upper()
    try:
        data = _HOLIDAYS_2026.get(cc)
        if not data:
            raise HTTPException(status_code=422, detail=f"No preset data for country_code={cc}. Supported: SE, AE, SA, MA")
        inserted = 0
        for date_str, name in data:
            hd = date.fromisoformat(date_str)
            if hd.year != body.year:
                continue
            existing = (await db.execute(
                select(PublicHoliday).where(
                    and_(
                        PublicHoliday.org_id == org_id,
                        PublicHoliday.country_code == cc,
                        PublicHoliday.holiday_date == hd,
                    )
                )
            )).scalar_one_or_none()
            if not existing:
                db.add(PublicHoliday(
                    id=uuid.uuid4(),
                    org_id=org_id,
                    country_code=cc,
                    holiday_date=hd,
                    name=name,
                    year=body.year,
                ))
                inserted += 1
        await db.commit()
        return {"inserted": inserted, "country_code": cc, "year": body.year}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"seed_holidays failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Entitlements ──────────────────────────────────────────────────────────────

@router.get("/api/hr/leave/entitlements")
async def list_entitlements(
    staff_id: Optional[uuid.UUID] = None,
    year: Optional[int] = None,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        q = select(LeaveEntitlement).where(LeaveEntitlement.org_id == org_id)
        if staff_id:
            q = q.where(LeaveEntitlement.staff_id == staff_id)
        if year:
            q = q.where(LeaveEntitlement.year == year)
        rows = (await db.execute(q)).scalars().all()
        return [_row(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_entitlements failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/leave/entitlements", status_code=201)
async def upsert_entitlement(
    body: EntitlementUpsert,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        existing = (await db.execute(
            select(LeaveEntitlement).where(
                and_(
                    LeaveEntitlement.org_id == org_id,
                    LeaveEntitlement.staff_id == body.staff_id,
                    LeaveEntitlement.leave_type == body.leave_type,
                    LeaveEntitlement.year == body.year,
                )
            )
        )).scalar_one_or_none()
        if existing:
            existing.days_allocated = body.days_allocated
            existing.carry_over_days = body.carry_over_days
            existing.carry_over_cap = body.carry_over_cap
        else:
            existing = LeaveEntitlement(
                id=uuid.uuid4(),
                org_id=org_id,
                **body.model_dump(),
            )
            db.add(existing)
        await db.commit()
        await db.refresh(existing)
        return _row(existing)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"upsert_entitlement failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/hr/leave/entitlements/{entitlement_id}", status_code=204)
async def delete_entitlement(
    entitlement_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(LeaveEntitlement).where(
                and_(LeaveEntitlement.org_id == org_id, LeaveEntitlement.id == entitlement_id)
            )
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Entitlement not found")
        await db.delete(row)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"delete_entitlement failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Leave Requests CRUD ───────────────────────────────────────────────────────

@router.get("/api/hr/leave")
async def list_leave(
    staff_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        q = select(LeaveRequest).where(LeaveRequest.org_id == org_id)
        if staff_id:
            q = q.where(LeaveRequest.staff_id == staff_id)
        if status:
            q = q.where(LeaveRequest.status == status)
        rows = (await db.execute(q.order_by(LeaveRequest.created_at.desc()))).scalars().all()

        staff_ids = {r.staff_id for r in rows}
        staff_map: dict[str, str] = {}
        if staff_ids:
            staff_rows = (await db.execute(
                select(Staff).where(Staff.id.in_(staff_ids))
            )).scalars().all()
            staff_map = {str(s.id): s.name for s in staff_rows}

        return [
            {**_row(r), "staff_name": staff_map.get(str(r.staff_id), "Unknown")}
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_leave failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/leave", status_code=201)
async def create_leave(
    body: LeaveRequestCreate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        if body.leave_type not in VALID_LEAVE_TYPES:
            raise HTTPException(status_code=422, detail=f"Invalid leave_type. Must be one of: {sorted(VALID_LEAVE_TYPES)}")
        if body.end_date < body.start_date:
            raise HTTPException(status_code=422, detail="end_date must be >= start_date")

        requester_email = user.get("email", "")
        row = LeaveRequest(
            id=uuid.uuid4(),
            org_id=org_id,
            requester_email=requester_email,
            **body.model_dump(),
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)

        # Notify: fire-and-forget email to submitter confirming receipt
        if requester_email:
            asyncio.create_task(_notify(
                requester_email,
                "Leave request submitted",
                f"<p>Your {body.leave_type} leave request from <b>{body.start_date}</b> to <b>{body.end_date}</b> has been submitted and is pending approval.</p>",
            ))

        return _row(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_leave failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/hr/leave/{leave_id}")
async def get_leave(
    leave_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(LeaveRequest).where(
                and_(LeaveRequest.org_id == org_id, LeaveRequest.id == leave_id)
            )
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Leave request not found")
        return _row(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"get_leave failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/hr/leave/{leave_id}")
async def update_leave(
    leave_id: uuid.UUID,
    body: LeaveRequestUpdate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(LeaveRequest).where(
                and_(LeaveRequest.org_id == org_id, LeaveRequest.id == leave_id)
            )
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Leave request not found")
        if row.status != "pending":
            raise HTTPException(status_code=422, detail="Only pending requests can be updated")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        await db.commit()
        await db.refresh(row)
        return _row(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"update_leave failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/hr/leave/{leave_id}", status_code=204)
async def cancel_leave(
    leave_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(LeaveRequest).where(
                and_(LeaveRequest.org_id == org_id, LeaveRequest.id == leave_id)
            )
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Leave request not found")
        if row.status not in ("pending",):
            raise HTTPException(status_code=422, detail="Only pending requests can be cancelled")
        row.status = "cancelled"
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"cancel_leave failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/leave/{leave_id}/approve", dependencies=_MANAGER_ONLY)
async def approve_leave(
    leave_id: uuid.UUID,
    body: ReviewBody = ReviewBody(),
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(LeaveRequest).where(
                and_(LeaveRequest.org_id == org_id, LeaveRequest.id == leave_id)
            )
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Leave request not found")
        if row.status != "pending":
            raise HTTPException(status_code=422, detail="Only pending requests can be approved")

        now = datetime.now(timezone.utc)
        row.status = "approved"
        row.approved_by = uuid.UUID(str(user["user_id"]))
        row.approved_at = now
        row.reviewer_note = body.reviewer_note

        kind = "sick" if row.leave_type == "sick" else "time_off"
        start_at = datetime(row.start_date.year, row.start_date.month, row.start_date.day, tzinfo=timezone.utc)
        end_at = datetime(row.end_date.year, row.end_date.month, row.end_date.day, tzinfo=timezone.utc) + timedelta(days=1)
        override = StaffAvailabilityOverride(
            id=uuid.uuid4(),
            org_id=org_id,
            staff_id=row.staff_id,
            kind=kind,
            start_at=start_at,
            end_at=end_at,
            reason=row.reason,
        )
        db.add(override)
        await db.flush()
        row.availability_override_id = override.id

        await db.commit()
        await db.refresh(row)

        if row.requester_email:
            asyncio.create_task(_notify(
                row.requester_email,
                "Leave request approved",
                f"<p>Your {row.leave_type} leave request from <b>{row.start_date}</b> to <b>{row.end_date}</b> has been <b style='color:green'>approved</b>."
                + (f"<br>Note: {body.reviewer_note}" if body.reviewer_note else "") + "</p>",
            ))

        return _row(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"approve_leave failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/leave/{leave_id}/reject", dependencies=_MANAGER_ONLY)
async def reject_leave(
    leave_id: uuid.UUID,
    body: RejectBody = RejectBody(),
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(LeaveRequest).where(
                and_(LeaveRequest.org_id == org_id, LeaveRequest.id == leave_id)
            )
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Leave request not found")
        if row.status != "pending":
            raise HTTPException(status_code=422, detail="Only pending requests can be rejected")
        row.status = "rejected"
        row.rejection_reason = body.rejection_reason
        row.reviewer_note = body.reviewer_note
        await db.commit()
        await db.refresh(row)

        if row.requester_email:
            asyncio.create_task(_notify(
                row.requester_email,
                "Leave request declined",
                f"<p>Your {row.leave_type} leave request from <b>{row.start_date}</b> to <b>{row.end_date}</b> has been <b style='color:red'>declined</b>."
                + (f"<br>Reason: {body.rejection_reason}" if body.rejection_reason else "") + "</p>",
            ))

        return _row(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"reject_leave failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
