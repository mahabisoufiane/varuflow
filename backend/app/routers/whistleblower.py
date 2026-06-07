"""Whistleblower — anonymous report submission and admin management.

NOTE: Submit and status endpoints are PUBLIC (no auth).
      Report listing and management endpoints require auth.

Endpoints
─────────
POST   /api/whistleblower/{org_id}/submit   → PUBLIC: submit a report
GET    /api/whistleblower/status/{token}    → PUBLIC: check own report status
GET    /api/whistleblower/reports           → AUTH: list reports for org
GET    /api/whistleblower/reports/{id}      → AUTH: full detail
PATCH  /api/whistleblower/reports/{id}      → AUTH: update status/assignment
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.whistleblower import WhistleblowerReport

router = APIRouter(prefix="/api/whistleblower", tags=["whistleblower"], dependencies=[Depends(require_module("compliance"))])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _report_out(r: WhistleblowerReport) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "org_id": str(r.org_id),
        "token": r.token,
        "category": r.category,
        "description": r.description,
        "is_anonymous": r.is_anonymous,
        "reporter_contact": r.reporter_contact,
        "status": r.status,
        "assigned_to_user_id": str(r.assigned_to_user_id) if r.assigned_to_user_id else None,
        "resolution_notes": r.resolution_notes,
        "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class ReportSubmitIn(BaseModel):
    category: str = Field(default="other")
    description: str = Field(min_length=10)
    is_anonymous: bool = Field(default=True)
    reporter_contact: Optional[str] = Field(default=None, max_length=500)


class ReportPatch(BaseModel):
    status: Optional[str] = None
    assigned_to_user_id: Optional[uuid.UUID] = None
    resolution_notes: Optional[str] = None


# ── Public Endpoints ───────────────────────────────────────────────────────────

@router.post("/{target_org_id}/submit", status_code=201)
async def submit_report(
    target_org_id: uuid.UUID,
    body: ReportSubmitIn,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """PUBLIC — no auth required. Submits a whistleblower report for the given org."""
    try:
        token = secrets.token_hex(32)  # 64 hex chars
        report = WhistleblowerReport(
            org_id=target_org_id,
            token=token,
            category=body.category,
            description=body.description,
            is_anonymous=body.is_anonymous,
            reporter_contact=body.reporter_contact if not body.is_anonymous else None,
            status="new",
            submitted_at=datetime.now(timezone.utc),
        )
        db.add(report)
        await db.commit()
        return {
            "token": token,
            "message": "Report submitted. Save your token to check status.",
        }
    except Exception as e:
        log.error("submit_report failed: %s", e, extra={"org_id": str(target_org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/status/{token}")
async def report_status(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """PUBLIC — no auth required. Returns minimal status info for the reporter."""
    try:
        report = await db.scalar(
            select(WhistleblowerReport).where(WhistleblowerReport.token == token)
        )
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        # Return only non-sensitive fields
        return {
            "status": report.status,
            "submitted_at": report.submitted_at.isoformat() if report.submitted_at else None,
            "category": report.category,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("report_status failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Auth-required Endpoints ────────────────────────────────────────────────────

@router.get("/reports")
async def list_reports(
    status: Optional[str] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = select(WhistleblowerReport).where(WhistleblowerReport.org_id == org_id)
        if status:
            q = q.where(WhistleblowerReport.status == status)
        q = q.order_by(WhistleblowerReport.submitted_at.desc())
        rows = (await db.execute(q)).scalars().all()
        return [_report_out(r) for r in rows]
    except Exception as e:
        log.error("list_reports failed: %s", e, extra={"org_id": str(org_id)})
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
            select(WhistleblowerReport).where(
                WhistleblowerReport.id == report_id,
                WhistleblowerReport.org_id == org_id,
            )
        )
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        return _report_out(report)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_report failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/reports/{report_id}")
async def patch_report(
    report_id: uuid.UUID,
    body: ReportPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        report = await db.scalar(
            select(WhistleblowerReport).where(
                WhistleblowerReport.id == report_id,
                WhistleblowerReport.org_id == org_id,
            )
        )
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        if body.status is not None:
            report.status = body.status
        if body.assigned_to_user_id is not None:
            report.assigned_to_user_id = body.assigned_to_user_id
        if body.resolution_notes is not None:
            report.resolution_notes = body.resolution_notes

        report.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(report)
        return _report_out(report)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_report failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
