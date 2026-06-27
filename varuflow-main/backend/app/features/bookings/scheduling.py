"""Scheduling router — roster view, overtime, shift swap requests."""
import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module, require_role
from app.features.auth.organization import OrgRole
from app.features.hr.shift import Shift
from app.features.hr.shift_swap import ShiftSwapRequest

logger = logging.getLogger(__name__)
# Roster building / overtime / swap approvals are manager-level (ADMIN+).
# Members view their OWN shifts via the self-service /hr/shifts page (separate
# /api/shifts router), so gating this roster router does not block self-service.
router = APIRouter(tags=["scheduling"], dependencies=[Depends(require_module("hr")), Depends(require_role(OrgRole.ADMIN))])


@router.get("/api/scheduling/roster")
async def get_roster(
    week_start: date,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return shifts for Mon-Sun grouped by staff."""
    try:
        org_id = member["org_id"]
        week_end = week_start + timedelta(days=7)
        result = await db.execute(text("""
            SELECT sh.id, sh.staff_id, s.name AS staff_name,
                   sh.start_at, sh.end_at, sh.notes
            FROM shifts sh
            JOIN staff s ON s.id = sh.staff_id
            WHERE sh.org_id = :org_id
              AND sh.start_at >= :start AND sh.start_at < :end
            ORDER BY s.name, sh.start_at
        """), {"org_id": org_id, "start": week_start, "end": week_end})
        rows = result.fetchall()
        roster: dict = {}
        for r in rows:
            sid = str(r.staff_id)
            if sid not in roster:
                roster[sid] = {"staff_id": sid, "staff_name": r.staff_name, "shifts": []}
            roster[sid]["shifts"].append({
                "id": str(r.id),
                "start_at": r.start_at.isoformat(),
                "end_at": r.end_at.isoformat(),
                "notes": r.notes,
            })
        return list(roster.values())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_roster failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/scheduling/overtime")
async def get_overtime(
    week_start: date,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return total hours per staff for the given week, flagging >40h."""
    try:
        org_id = member["org_id"]
        week_end = week_start + timedelta(days=7)
        result = await db.execute(text("""
            SELECT sh.staff_id, s.name AS staff_name,
                   SUM(EXTRACT(EPOCH FROM (sh.end_at - sh.start_at)) / 3600) AS total_hours
            FROM shifts sh
            JOIN staff s ON s.id = sh.staff_id
            WHERE sh.org_id = :org_id
              AND sh.start_at >= :start AND sh.start_at < :end
            GROUP BY sh.staff_id, s.name
            ORDER BY total_hours DESC
        """), {"org_id": org_id, "start": week_start, "end": week_end})
        return [
            {
                "staff_id": str(r.staff_id),
                "staff_name": r.staff_name,
                "total_hours": round(float(r.total_hours), 1),
                "is_overtime": float(r.total_hours) > 40,
            }
            for r in result.fetchall()
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_overtime failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


# ─── Shift Swap Requests ─────────────────────────────────────────────────────

class SwapCreate(BaseModel):
    requester_shift_id: str
    target_staff_id: str

class SwapDecision(BaseModel):
    status: str  # approved | rejected
    manager_notes: str | None = None


@router.get("/api/scheduling/swap-requests")
async def list_swap_requests(
    status: str | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(ShiftSwapRequest).where(ShiftSwapRequest.org_id == org_id)
        if status:
            q = q.where(ShiftSwapRequest.status == status)
        rows = (await db.execute(q.order_by(ShiftSwapRequest.created_at.desc()))).scalars().all()
        return [_swap_dict(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_swap_requests failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/scheduling/swap-requests", status_code=201)
async def create_swap_request(body: SwapCreate, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        shift = (await db.execute(select(Shift).where(Shift.id == body.requester_shift_id, Shift.org_id == org_id))).scalar_one_or_none()
        if not shift:
            raise HTTPException(status_code=404, detail="Shift not found")
        rec = ShiftSwapRequest(
            org_id=org_id, requester_shift_id=body.requester_shift_id,
            requester_staff_id=shift.staff_id, target_staff_id=body.target_staff_id,
        )
        db.add(rec)
        await db.commit()
        await db.refresh(rec)
        return _swap_dict(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_swap_request failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/scheduling/swap-requests/{req_id}")
async def decide_swap_request(req_id: str, body: SwapDecision, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        rec = (await db.execute(select(ShiftSwapRequest).where(ShiftSwapRequest.id == req_id, ShiftSwapRequest.org_id == org_id))).scalar_one_or_none()
        if not rec:
            raise HTTPException(status_code=404, detail="Swap request not found")
        if rec.status != "pending":
            raise HTTPException(status_code=409, detail="Already resolved")
        if body.status not in ("approved", "rejected"):
            raise HTTPException(status_code=422, detail="status must be approved or rejected")
        rec.status = body.status
        rec.manager_notes = body.manager_notes
        rec.resolved_at = datetime.now(timezone.utc)
        if body.status == "approved":
            shift = (await db.execute(select(Shift).where(Shift.id == rec.requester_shift_id))).scalar_one_or_none()
            if shift:
                shift.staff_id = rec.target_staff_id
        await db.commit()
        await db.refresh(rec)
        return _swap_dict(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"decide_swap_request failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


def _swap_dict(r: ShiftSwapRequest) -> dict:
    return {
        "id": str(r.id),
        "requester_shift_id": str(r.requester_shift_id),
        "requester_staff_id": str(r.requester_staff_id),
        "target_staff_id": str(r.target_staff_id),
        "target_shift_id": str(r.target_shift_id) if r.target_shift_id else None,
        "status": r.status,
        "manager_notes": r.manager_notes,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
    }
