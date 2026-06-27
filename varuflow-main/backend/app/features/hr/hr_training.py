"""Training Records router — certifications and required training per staff member."""
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.features.bookings.models import Staff
from .hr_onboarding_training import EmployeeTrainingRecord
from .training_management import MandatoryTrainingRequirement, TrainingRequest

logger = logging.getLogger(__name__)
router = APIRouter(tags=["hr-training"], dependencies=[Depends(require_module("hr"))])

_CATEGORIES = {"safety", "compliance", "technical", "soft_skills", "product", "language", "other"}
_STATUSES = {"not_started", "in_progress", "completed", "expired"}


class TrainingCreate(BaseModel):
    staff_id: str
    training_name: str
    provider: str | None = None
    category: str = "other"
    is_required: bool = False
    status: str = "not_started"
    completed_at: date | None = None
    expiry_date: date | None = None
    required_by_date: date | None = None
    certificate_url: str | None = None
    notes: str | None = None

class TrainingUpdate(BaseModel):
    training_name: str | None = None
    provider: str | None = None
    category: str | None = None
    is_required: bool | None = None
    status: str | None = None
    completed_at: date | None = None
    expiry_date: date | None = None
    required_by_date: date | None = None
    certificate_url: str | None = None
    notes: str | None = None


@router.get("/api/hr/training")
async def list_training(
    staff_id: str | None = None,
    category: str | None = None,
    status: str | None = None,
    is_required: bool | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(EmployeeTrainingRecord).where(EmployeeTrainingRecord.org_id == org_id)
        if staff_id:
            q = q.where(EmployeeTrainingRecord.staff_id == staff_id)
        if category:
            q = q.where(EmployeeTrainingRecord.category == category)
        if status:
            q = q.where(EmployeeTrainingRecord.status == status)
        if is_required is not None:
            q = q.where(EmployeeTrainingRecord.is_required == is_required)
        rows = (await db.execute(q.order_by(EmployeeTrainingRecord.training_name))).scalars().all()
        return [_rec_dict(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_training failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/hr/training/alerts")
async def training_alerts(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return overdue and expiring-soon training records across all staff."""
    try:
        org_id = member["org_id"]
        today = date.today()
        result = await db.execute(text("""
            SELECT
                tr.id, tr.staff_id, s.name AS staff_name,
                tr.training_name, tr.category, tr.status, tr.is_required,
                tr.expiry_date, tr.required_by_date,
                CASE
                    WHEN tr.expiry_date < :today THEN 'expired'
                    WHEN tr.expiry_date <= :today + INTERVAL '30 days' THEN 'expiring_30'
                    WHEN tr.expiry_date <= :today + INTERVAL '60 days' THEN 'expiring_60'
                    WHEN tr.required_by_date < :today AND tr.status != 'completed' THEN 'overdue'
                    ELSE NULL
                END AS alert_type
            FROM employee_training_records tr
            JOIN staff s ON s.id = tr.staff_id
            WHERE tr.org_id = :org_id
              AND (
                (tr.expiry_date IS NOT NULL AND tr.expiry_date <= :today + INTERVAL '60 days')
                OR (tr.required_by_date < :today AND tr.status != 'completed')
              )
            ORDER BY COALESCE(tr.expiry_date, tr.required_by_date)
            LIMIT 100
        """), {"org_id": org_id, "today": today})
        rows = result.fetchall()
        return [
            {
                "id": str(r.id), "staff_id": str(r.staff_id), "staff_name": r.staff_name,
                "training_name": r.training_name, "category": r.category,
                "status": r.status, "is_required": r.is_required,
                "expiry_date": r.expiry_date.isoformat() if r.expiry_date else None,
                "required_by_date": r.required_by_date.isoformat() if r.required_by_date else None,
                "alert_type": r.alert_type,
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"training_alerts failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/hr/training/summary")
async def training_summary(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Per-staff summary of training completion."""
    try:
        org_id = member["org_id"]
        result = await db.execute(text("""
            SELECT
                tr.staff_id, s.name AS staff_name,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE tr.status = 'completed') AS completed,
                COUNT(*) FILTER (WHERE tr.is_required AND tr.status != 'completed') AS required_incomplete,
                COUNT(*) FILTER (WHERE tr.expiry_date < CURRENT_DATE) AS expired
            FROM employee_training_records tr
            JOIN staff s ON s.id = tr.staff_id
            WHERE tr.org_id = :org_id
            GROUP BY tr.staff_id, s.name
            ORDER BY s.name
        """), {"org_id": org_id})
        return [
            {
                "staff_id": str(r.staff_id), "staff_name": r.staff_name,
                "total": r.total, "completed": r.completed,
                "required_incomplete": r.required_incomplete, "expired": r.expired,
                "completion_pct": round(r.completed / r.total * 100, 1) if r.total > 0 else 0,
            }
            for r in result.fetchall()
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"training_summary failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/training", status_code=201)
async def create_training(
    body: TrainingCreate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        if body.status not in _STATUSES:
            raise HTTPException(status_code=422, detail=f"status must be one of {_STATUSES}")
        rec = EmployeeTrainingRecord(
            org_id=org_id, staff_id=body.staff_id,
            training_name=body.training_name, provider=body.provider,
            category=body.category if body.category in _CATEGORIES else "other",
            status=body.status, is_required=body.is_required,
            completed_at=body.completed_at, expiry_date=body.expiry_date,
            required_by_date=body.required_by_date,
            certificate_url=body.certificate_url, notes=body.notes,
        )
        db.add(rec)
        await db.commit()
        await db.refresh(rec)
        return _rec_dict(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_training failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/hr/training/{record_id}")
async def update_training(
    record_id: str,
    body: TrainingUpdate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        rec = (await db.execute(
            select(EmployeeTrainingRecord).where(
                EmployeeTrainingRecord.id == record_id, EmployeeTrainingRecord.org_id == org_id
            )
        )).scalar_one_or_none()
        if not rec:
            raise HTTPException(status_code=404, detail="Training record not found")
        data = body.model_dump(exclude_none=True)
        if "status" in data and data["status"] not in _STATUSES:
            raise HTTPException(status_code=422, detail=f"status must be one of {_STATUSES}")
        for field, val in data.items():
            setattr(rec, field, val)
        # Auto-set completed_at when marking complete
        if data.get("status") == "completed" and not rec.completed_at:
            rec.completed_at = date.today()
        await db.commit()
        await db.refresh(rec)
        return _rec_dict(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_training failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/hr/training/{record_id}", status_code=204)
async def delete_training(
    record_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        rec = (await db.execute(
            select(EmployeeTrainingRecord).where(
                EmployeeTrainingRecord.id == record_id, EmployeeTrainingRecord.org_id == org_id
            )
        )).scalar_one_or_none()
        if not rec:
            raise HTTPException(status_code=404, detail="Training record not found")
        await db.delete(rec)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_training failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


def _rec_dict(r: EmployeeTrainingRecord) -> dict:
    today = date.today()
    is_expired = bool(r.expiry_date and r.expiry_date < today)
    expiring_30 = bool(r.expiry_date and not is_expired and (r.expiry_date - today).days <= 30)
    expiring_60 = bool(r.expiry_date and not is_expired and not expiring_30 and (r.expiry_date - today).days <= 60)
    is_overdue = bool(r.required_by_date and r.required_by_date < today and r.status != "completed")
    return {
        "id": str(r.id), "staff_id": str(r.staff_id),
        "training_name": r.training_name, "provider": r.provider,
        "category": r.category, "status": r.status, "is_required": r.is_required,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "expiry_date": r.expiry_date.isoformat() if r.expiry_date else None,
        "required_by_date": r.required_by_date.isoformat() if r.required_by_date else None,
        "certificate_url": r.certificate_url, "notes": r.notes,
        "is_expired": is_expired, "expiring_30": expiring_30, "expiring_60": expiring_60, "is_overdue": is_overdue,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ── Mandatory Training Requirements ──────────────────────────────────────────

class RequirementCreate(BaseModel):
    job_role: str
    training_name: str
    category: str = "other"
    description: Optional[str] = None


@router.get("/api/hr/training/requirements")
async def list_requirements(
    job_role: Optional[str] = None,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        q = select(MandatoryTrainingRequirement).where(
            MandatoryTrainingRequirement.org_id == org_id
        )
        if job_role:
            q = q.where(MandatoryTrainingRequirement.job_role == job_role)
        rows = (await db.execute(q.order_by(
            MandatoryTrainingRequirement.job_role,
            MandatoryTrainingRequirement.training_name,
        ))).scalars().all()
        return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_requirements failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/training/requirements", status_code=201)
async def create_requirement(
    body: RequirementCreate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        req = MandatoryTrainingRequirement(
            id=uuid.uuid4(), org_id=org_id,
            job_role=body.job_role, training_name=body.training_name,
            category=body.category if body.category in _CATEGORIES else "other",
            description=body.description,
        )
        db.add(req)
        await db.commit()
        await db.refresh(req)
        return {c.name: getattr(req, c.name) for c in req.__table__.columns}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_requirement failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/hr/training/requirements/{req_id}", status_code=204)
async def delete_requirement(
    req_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        req = (await db.execute(
            select(MandatoryTrainingRequirement).where(
                and_(MandatoryTrainingRequirement.org_id == org_id,
                     MandatoryTrainingRequirement.id == req_id)
            )
        )).scalar_one_or_none()
        if not req:
            raise HTTPException(status_code=404, detail="Requirement not found")
        await db.delete(req)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_requirement failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Training Requests ─────────────────────────────────────────────────────────

class TrainingRequestCreate(BaseModel):
    staff_id: uuid.UUID
    training_name: str
    provider: Optional[str] = None
    estimated_cost: Optional[float] = None
    justification: Optional[str] = None


class TrainingRequestAction(BaseModel):
    manager_notes: Optional[str] = None


@router.get("/api/hr/training/requests")
async def list_training_requests(
    staff_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        q = (
            select(TrainingRequest, Staff)
            .join(Staff, Staff.id == TrainingRequest.staff_id)
            .where(TrainingRequest.org_id == org_id)
        )
        if staff_id:
            q = q.where(TrainingRequest.staff_id == staff_id)
        if status:
            q = q.where(TrainingRequest.status == status)
        q = q.order_by(TrainingRequest.created_at.desc())
        rows = (await db.execute(q)).all()
        return [
            {
                **{c.name: getattr(tr, c.name) for c in tr.__table__.columns},
                "staff_name": staff.name,
            }
            for tr, staff in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_training_requests failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/training/requests", status_code=201)
async def create_training_request(
    body: TrainingRequestCreate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        tr = TrainingRequest(
            id=uuid.uuid4(), org_id=org_id,
            staff_id=body.staff_id, training_name=body.training_name,
            provider=body.provider, estimated_cost=body.estimated_cost,
            justification=body.justification, status="pending",
        )
        db.add(tr)
        await db.commit()
        await db.refresh(tr)
        return {c.name: getattr(tr, c.name) for c in tr.__table__.columns}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_training_request failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/training/requests/{req_id}/approve")
async def approve_training_request(
    req_id: uuid.UUID,
    body: TrainingRequestAction = TrainingRequestAction(),
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        tr = (await db.execute(
            select(TrainingRequest).where(
                and_(TrainingRequest.org_id == org_id, TrainingRequest.id == req_id)
            )
        )).scalar_one_or_none()
        if not tr:
            raise HTTPException(status_code=404, detail="Training request not found")
        if tr.status != "pending":
            raise HTTPException(status_code=409, detail="Only pending requests can be approved")
        tr.status = "approved"
        tr.manager_notes = body.manager_notes
        tr.resolved_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(tr)
        return {c.name: getattr(tr, c.name) for c in tr.__table__.columns}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"approve_training_request failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/training/requests/{req_id}/reject")
async def reject_training_request(
    req_id: uuid.UUID,
    body: TrainingRequestAction,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        tr = (await db.execute(
            select(TrainingRequest).where(
                and_(TrainingRequest.org_id == org_id, TrainingRequest.id == req_id)
            )
        )).scalar_one_or_none()
        if not tr:
            raise HTTPException(status_code=404, detail="Training request not found")
        if tr.status != "pending":
            raise HTTPException(status_code=409, detail="Only pending requests can be rejected")
        tr.status = "rejected"
        tr.manager_notes = body.manager_notes
        tr.resolved_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(tr)
        return {c.name: getattr(tr, c.name) for c in tr.__table__.columns}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"reject_training_request failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
