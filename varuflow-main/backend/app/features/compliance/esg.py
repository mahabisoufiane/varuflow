"""ESG Reports — Environmental, Social, and Governance reporting.

Endpoints
─────────
GET    /api/esg/reports                   → list reports for org
POST   /api/esg/reports                   → create report
GET    /api/esg/reports/{id}              → detail
PATCH  /api/esg/reports/{id}              → update fields
DELETE /api/esg/reports/{id}              → delete (draft only; 409 if published)
POST   /api/esg/reports/{id}/publish      → publish report
POST   /api/esg/reports/{id}/auto-populate → fill E-metrics from carbon data
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from .carbon_models import CarbonEntry
from .esg_models import EsgReport
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/esg", tags=["esg"], dependencies=[Depends(require_module("analytics"))])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _report_out(r: EsgReport) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "org_id": str(r.org_id),
        "title": r.title,
        "report_year": r.report_year,
        "status": r.status,
        "published_at": r.published_at.isoformat() if r.published_at else None,
        # E
        "total_co2_tonnes": float(r.total_co2_tonnes) if r.total_co2_tonnes is not None else None,
        "co2_per_revenue": float(r.co2_per_revenue) if r.co2_per_revenue is not None else None,
        "renewable_energy_pct": float(r.renewable_energy_pct) if r.renewable_energy_pct is not None else None,
        "waste_recycled_pct": float(r.waste_recycled_pct) if r.waste_recycled_pct is not None else None,
        # S
        "employee_count": r.employee_count,
        "female_leadership_pct": float(r.female_leadership_pct) if r.female_leadership_pct is not None else None,
        "training_hours_per_employee": float(r.training_hours_per_employee) if r.training_hours_per_employee is not None else None,
        "employee_satisfaction_score": float(r.employee_satisfaction_score) if r.employee_satisfaction_score is not None else None,
        "injury_rate": float(r.injury_rate) if r.injury_rate is not None else None,
        # G
        "audit_complete": r.audit_complete,
        "whistleblower_mechanism": r.whistleblower_mechanism,
        "anti_corruption_training_pct": float(r.anti_corruption_training_pct) if r.anti_corruption_training_pct is not None else None,
        "board_diversity_pct": float(r.board_diversity_pct) if r.board_diversity_pct is not None else None,
        "notes": r.notes,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class EsgReportIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    report_year: int
    # E
    total_co2_tonnes: Optional[float] = None
    co2_per_revenue: Optional[float] = None
    renewable_energy_pct: Optional[float] = None
    waste_recycled_pct: Optional[float] = None
    # S
    employee_count: Optional[int] = None
    female_leadership_pct: Optional[float] = None
    training_hours_per_employee: Optional[float] = None
    employee_satisfaction_score: Optional[float] = None
    injury_rate: Optional[float] = None
    # G
    audit_complete: Optional[bool] = None
    whistleblower_mechanism: Optional[bool] = None
    anti_corruption_training_pct: Optional[float] = None
    board_diversity_pct: Optional[float] = None
    notes: Optional[str] = None


class EsgReportPatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=300)
    report_year: Optional[int] = None
    total_co2_tonnes: Optional[float] = None
    co2_per_revenue: Optional[float] = None
    renewable_energy_pct: Optional[float] = None
    waste_recycled_pct: Optional[float] = None
    employee_count: Optional[int] = None
    female_leadership_pct: Optional[float] = None
    training_hours_per_employee: Optional[float] = None
    employee_satisfaction_score: Optional[float] = None
    injury_rate: Optional[float] = None
    audit_complete: Optional[bool] = None
    whistleblower_mechanism: Optional[bool] = None
    anti_corruption_training_pct: Optional[float] = None
    board_diversity_pct: Optional[float] = None
    notes: Optional[str] = None


_METRIC_FIELDS = (
    "total_co2_tonnes", "co2_per_revenue", "renewable_energy_pct", "waste_recycled_pct",
    "employee_count", "female_leadership_pct", "training_hours_per_employee",
    "employee_satisfaction_score", "injury_rate", "audit_complete", "whistleblower_mechanism",
    "anti_corruption_training_pct", "board_diversity_pct", "notes",
)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/reports")
async def list_reports(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        rows = (await db.execute(
            select(EsgReport).where(EsgReport.org_id == org_id)
            .order_by(EsgReport.report_year.desc())
        )).scalars().all()
        return [_report_out(r) for r in rows]
    except Exception as e:
        log.error("list_esg_reports failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/reports", status_code=201)
async def create_report(
    body: EsgReportIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        report = EsgReport(
            org_id=org_id,
            title=body.title,
            report_year=body.report_year,
            status="draft",
        )
        for field in _METRIC_FIELDS:
            val = getattr(body, field)
            if val is not None:
                setattr(report, field, val)
        db.add(report)
        await db.commit()
        await db.refresh(report)
        return _report_out(report)
    except Exception as e:
        log.error("create_esg_report failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/reports/{report_id}")
async def get_report(
    report_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        report = await db.scalar(
            select(EsgReport).where(EsgReport.id == report_id, EsgReport.org_id == org_id)
        )
        if not report:
            raise HTTPException(status_code=404, detail="ESG report not found")
        return _report_out(report)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_esg_report failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/reports/{report_id}")
async def patch_report(
    report_id: uuid.UUID,
    body: EsgReportPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        report = await db.scalar(
            select(EsgReport).where(EsgReport.id == report_id, EsgReport.org_id == org_id)
        )
        if not report:
            raise HTTPException(status_code=404, detail="ESG report not found")

        if body.title is not None:
            report.title = body.title
        if body.report_year is not None:
            report.report_year = body.report_year
        for field in _METRIC_FIELDS:
            val = getattr(body, field)
            if val is not None:
                setattr(report, field, val)

        report.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(report)
        return _report_out(report)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_esg_report failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/reports/{report_id}", status_code=204)
async def delete_report(
    report_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        report = await db.scalar(
            select(EsgReport).where(EsgReport.id == report_id, EsgReport.org_id == org_id)
        )
        if not report:
            raise HTTPException(status_code=404, detail="ESG report not found")
        if report.status == "published":
            raise HTTPException(status_code=409, detail="Cannot delete a published report")
        await db.delete(report)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_esg_report failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/reports/{report_id}/publish")
async def publish_report(
    report_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        report = await db.scalar(
            select(EsgReport).where(EsgReport.id == report_id, EsgReport.org_id == org_id)
        )
        if not report:
            raise HTTPException(status_code=404, detail="ESG report not found")
        report.status = "published"
        report.published_at = datetime.now(timezone.utc)
        report.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(report)
        return _report_out(report)
    except HTTPException:
        raise
    except Exception as e:
        log.error("publish_esg_report failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/reports/{report_id}/auto-populate")
async def auto_populate_report(
    report_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Auto-fill environmental metrics from carbon data for the report year."""
    org_id = _org_id(ctx)
    try:
        report = await db.scalar(
            select(EsgReport).where(EsgReport.id == report_id, EsgReport.org_id == org_id)
        )
        if not report:
            raise HTTPException(status_code=404, detail="ESG report not found")

        year = report.report_year
        carbon_rows = (await db.execute(
            select(CarbonEntry).where(
                CarbonEntry.org_id == org_id,
                CarbonEntry.period_start >= date(year, 1, 1),
                CarbonEntry.period_start <= date(year, 12, 31),
            )
        )).scalars().all()

        total_co2_kg = sum(float(e.co2_kg) for e in carbon_rows)
        total_co2_tonnes = round(total_co2_kg / 1000, 4)
        report.total_co2_tonnes = Decimal(str(total_co2_tonnes))
        report.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(report)
        return _report_out(report)
    except HTTPException:
        raise
    except Exception as e:
        log.error("auto_populate_esg_report failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
