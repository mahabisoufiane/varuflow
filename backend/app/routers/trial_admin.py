"""Admin endpoints for trial onboarding sequences dashboard."""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.trial_sequences import (
    TrialEmailSend,
    TrialEnrollment,
    TrialSequence,
    TrialSequenceStep,
)

router = APIRouter(tags=["trial-admin"])
log = logging.getLogger(__name__)


# ── Auth dependency ────────────────────────────────────────────────────────────


async def _require_admin(
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
) -> None:
    key = getattr(settings, "ADMIN_API_KEY", "") or ""
    if not key or not x_admin_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")
    if not secrets.compare_digest(x_admin_key, key):
        raise HTTPException(status_code=401, detail="Invalid admin key")


# ── Schemas ────────────────────────────────────────────────────────────────────


class SequenceRow(BaseModel):
    id: str
    name: str
    locale: str
    enabled: bool
    steps_count: int
    active_enrollments: int
    completion_rate: float


class EnrollmentRow(BaseModel):
    id: str
    org_id: str
    user_email: str
    current_step: int
    next_send_at: Optional[str]
    locale: str
    exit_reason: Optional[str]
    completed_at: Optional[str]


class StepStatRow(BaseModel):
    step_number: int
    template_key: str
    sent: int
    opened: int
    clicked: int


class SummaryResponse(BaseModel):
    sequences: list[SequenceRow]
    total_active_enrollments: int
    emails_sent_this_week: int
    conversion_rate: float
    avg_completion_rate: float


class ForceExitBody(BaseModel):
    reason: str = "manual"


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/api/admin/trial/sequences", response_model=SummaryResponse)
async def list_sequences(
    _: None = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> SummaryResponse:
    try:
        # Load all sequences
        seq_result = await db.execute(select(TrialSequence))
        sequences = seq_result.scalars().all()

        rows: list[SequenceRow] = []
        total_active = 0

        for seq in sequences:
            # Step count
            steps_count_result = await db.execute(
                select(func.count()).select_from(TrialSequenceStep).where(
                    TrialSequenceStep.sequence_id == seq.id
                )
            )
            steps_count = steps_count_result.scalar() or 0

            # Active enrollments (not exited, not completed)
            active_result = await db.execute(
                select(func.count()).select_from(TrialEnrollment).where(
                    TrialEnrollment.sequence_id == seq.id,
                    TrialEnrollment.exited_at.is_(None),
                    TrialEnrollment.completed_at.is_(None),
                )
            )
            active = active_result.scalar() or 0
            total_active += active

            # Completion rate
            total_result = await db.execute(
                select(func.count()).select_from(TrialEnrollment).where(
                    TrialEnrollment.sequence_id == seq.id
                )
            )
            total = total_result.scalar() or 0

            completed_result = await db.execute(
                select(func.count()).select_from(TrialEnrollment).where(
                    TrialEnrollment.sequence_id == seq.id,
                    TrialEnrollment.completed_at.isnot(None),  # type: ignore[arg-type]
                )
            )
            completed = completed_result.scalar() or 0

            completion_rate = round((completed / total * 100) if total > 0 else 0.0, 1)

            rows.append(
                SequenceRow(
                    id=str(seq.id),
                    name=seq.name,
                    locale=seq.locale,
                    enabled=seq.enabled,
                    steps_count=steps_count,
                    active_enrollments=active,
                    completion_rate=completion_rate,
                )
            )

        # Emails sent this week
        from datetime import timedelta

        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        week_sends_result = await db.execute(
            select(func.count()).select_from(TrialEmailSend).where(
                TrialEmailSend.sent_at >= week_ago
            )
        )
        emails_sent_this_week = week_sends_result.scalar() or 0

        # Conversion rate: enrollments with exit_reason=converted / total enrollments
        total_enrollments_result = await db.execute(
            select(func.count()).select_from(TrialEnrollment)
        )
        total_enrollments = total_enrollments_result.scalar() or 0

        converted_result = await db.execute(
            select(func.count()).select_from(TrialEnrollment).where(
                TrialEnrollment.exit_reason == "converted"
            )
        )
        converted = converted_result.scalar() or 0
        conversion_rate = round((converted / total_enrollments * 100) if total_enrollments > 0 else 0.0, 1)

        avg_completion = round(
            sum(r.completion_rate for r in rows) / len(rows) if rows else 0.0, 1
        )

        return SummaryResponse(
            sequences=rows,
            total_active_enrollments=total_active,
            emails_sent_this_week=emails_sent_this_week,
            conversion_rate=conversion_rate,
            avg_completion_rate=avg_completion,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_sequences failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/admin/trial/sequences/{sequence_id}/enrollments", response_model=list[EnrollmentRow])
async def list_enrollments(
    sequence_id: str,
    _: None = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[EnrollmentRow]:
    try:
        result = await db.execute(
            select(TrialEnrollment)
            .where(TrialEnrollment.sequence_id == sequence_id)
            .limit(100)
        )
        enrollments = result.scalars().all()

        return [
            EnrollmentRow(
                id=str(e.id),
                org_id=str(e.org_id),
                user_email=str(e.user_id),  # user_id used as identifier; join to users table if email needed
                current_step=e.current_step,
                next_send_at=e.next_send_at.isoformat() if e.next_send_at else None,
                locale=e.locale,
                exit_reason=e.exit_reason,
                completed_at=e.completed_at.isoformat() if e.completed_at else None,
            )
            for e in enrollments
        ]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_enrollments failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/admin/trial/sequences/{sequence_id}/stats", response_model=list[StepStatRow])
async def sequence_stats(
    sequence_id: str,
    _: None = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[StepStatRow]:
    try:
        steps_result = await db.execute(
            select(TrialSequenceStep)
            .where(TrialSequenceStep.sequence_id == sequence_id)
            .order_by(TrialSequenceStep.step_number)
        )
        steps = steps_result.scalars().all()

        # Collect enrollment IDs for this sequence to scope TrialEmailSend queries
        enroll_ids_result = await db.execute(
            select(TrialEnrollment.id).where(
                TrialEnrollment.sequence_id == sequence_id
            )
        )
        enroll_ids = [row[0] for row in enroll_ids_result.all()]

        rows: list[StepStatRow] = []
        for step in steps:
            if not enroll_ids:
                rows.append(
                    StepStatRow(
                        step_number=step.step_number,
                        template_key=step.email_template_key,
                        sent=0,
                        opened=0,
                        clicked=0,
                    )
                )
                continue

            sent_result = await db.execute(
                select(func.count()).select_from(TrialEmailSend).where(
                    TrialEmailSend.enrollment_id.in_(enroll_ids),
                    TrialEmailSend.step_number == step.step_number,
                )
            )
            sent = sent_result.scalar() or 0

            opened_result = await db.execute(
                select(func.count()).select_from(TrialEmailSend).where(
                    TrialEmailSend.enrollment_id.in_(enroll_ids),
                    TrialEmailSend.step_number == step.step_number,
                    TrialEmailSend.opened_at.isnot(None),  # type: ignore[arg-type]
                )
            )
            opened = opened_result.scalar() or 0

            clicked_result = await db.execute(
                select(func.count()).select_from(TrialEmailSend).where(
                    TrialEmailSend.enrollment_id.in_(enroll_ids),
                    TrialEmailSend.step_number == step.step_number,
                    TrialEmailSend.clicked_at.isnot(None),  # type: ignore[arg-type]
                )
            )
            clicked = clicked_result.scalar() or 0

            rows.append(
                StepStatRow(
                    step_number=step.step_number,
                    template_key=step.email_template_key,
                    sent=sent,
                    opened=opened,
                    clicked=clicked,
                )
            )

        return rows
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"sequence_stats failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/admin/trial/enrollments/{enrollment_id}/exit", status_code=200)
async def force_exit_enrollment(
    enrollment_id: str,
    body: ForceExitBody,
    _: None = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        result = await db.execute(
            select(TrialEnrollment).where(TrialEnrollment.id == enrollment_id)
        )
        enrollment = result.scalar_one_or_none()
        if enrollment is None:
            raise HTTPException(status_code=404, detail="Enrollment not found")

        enrollment.exited_at = datetime.now(timezone.utc)
        enrollment.exit_reason = body.reason
        await db.commit()

        return {"ok": True, "exit_reason": body.reason}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"force_exit_enrollment failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
