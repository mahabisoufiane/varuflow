"""Quality control router: checklists and inspections."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from .quality_control import QcChecklist, QcInspection
from app.middleware.plan_check import require_module

log = logging.getLogger(__name__)
router = APIRouter(
    dependencies=[Depends(require_module("inventory"))],
)

VALID_APPLIES_TO = {"work_order", "batch"}
VALID_STATUSES = {"pending", "passed", "failed"}


class ChecklistCreate(BaseModel):
    name: str
    applies_to: str
    items: List[Any] = []


class ChecklistUpdate(BaseModel):
    name: Optional[str] = None
    applies_to: Optional[str] = None
    items: Optional[List[Any]] = None
    is_active: Optional[bool] = None


class InspectionCreate(BaseModel):
    checklist_id: uuid.UUID
    work_order_id: Optional[uuid.UUID] = None
    batch_id: Optional[uuid.UUID] = None
    inspector_name: Optional[str] = None
    notes: Optional[str] = None


class InspectionSubmit(BaseModel):
    status: str
    results: dict
    inspector_name: Optional[str] = None
    notes: Optional[str] = None


def _row(obj: Any) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


# ── Checklists ────────────────────────────────────────────────────────────────

@router.get("/api/manufacturing/qc/checklists")
async def list_checklists(
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        rows = (await db.execute(
            select(QcChecklist).where(QcChecklist.org_id == org_id).order_by(QcChecklist.name)
        )).scalars().all()
        return [_row(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_checklists failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/manufacturing/qc/checklists", status_code=201)
async def create_checklist(
    body: ChecklistCreate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        if body.applies_to not in VALID_APPLIES_TO:
            raise HTTPException(status_code=422, detail=f"applies_to must be one of: {VALID_APPLIES_TO}")
        row = QcChecklist(id=uuid.uuid4(), org_id=org_id, **body.model_dump())
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _row(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_checklist failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/manufacturing/qc/checklists/{checklist_id}")
async def update_checklist(
    checklist_id: uuid.UUID,
    body: ChecklistUpdate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(QcChecklist).where(and_(QcChecklist.org_id == org_id, QcChecklist.id == checklist_id))
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Checklist not found")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        await db.commit()
        await db.refresh(row)
        return _row(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"update_checklist failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/manufacturing/qc/checklists/{checklist_id}", status_code=204)
async def delete_checklist(
    checklist_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(QcChecklist).where(and_(QcChecklist.org_id == org_id, QcChecklist.id == checklist_id))
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Checklist not found")
        await db.delete(row)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"delete_checklist failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Inspections ───────────────────────────────────────────────────────────────

@router.get("/api/manufacturing/qc/inspections")
async def list_inspections(
    work_order_id: Optional[uuid.UUID] = None,
    batch_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        q = select(QcInspection).where(QcInspection.org_id == org_id)
        if work_order_id:
            q = q.where(QcInspection.work_order_id == work_order_id)
        if batch_id:
            q = q.where(QcInspection.batch_id == batch_id)
        if status:
            q = q.where(QcInspection.status == status)
        rows = (await db.execute(q.order_by(QcInspection.created_at.desc()))).scalars().all()
        return [_row(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_inspections failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/manufacturing/qc/inspections", status_code=201)
async def create_inspection(
    body: InspectionCreate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        checklist = (await db.execute(
            select(QcChecklist).where(and_(QcChecklist.org_id == org_id, QcChecklist.id == body.checklist_id))
        )).scalar_one_or_none()
        if not checklist:
            raise HTTPException(status_code=404, detail="Checklist not found")
        row = QcInspection(id=uuid.uuid4(), org_id=org_id, **body.model_dump())
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _row(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_inspection failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/manufacturing/qc/inspections/{inspection_id}")
async def get_inspection(
    inspection_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(QcInspection).where(and_(QcInspection.org_id == org_id, QcInspection.id == inspection_id))
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Inspection not found")
        return _row(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"get_inspection failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/manufacturing/qc/inspections/{inspection_id}")
async def update_inspection(
    inspection_id: uuid.UUID,
    body: InspectionSubmit,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Submit inspection results. Sets status=passed|failed and inspected_at."""
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(QcInspection).where(and_(QcInspection.org_id == org_id, QcInspection.id == inspection_id))
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Inspection not found")
        if body.status not in VALID_STATUSES:
            raise HTTPException(status_code=422, detail=f"status must be one of: {VALID_STATUSES}")
        row.status = body.status
        row.results = body.results
        if body.inspector_name is not None:
            row.inspector_name = body.inspector_name
        if body.notes is not None:
            row.notes = body.notes
        row.inspected_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(row)
        return _row(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"update_inspection failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
