"""NPS (Net Promoter Score) survey service.

Pure helpers
------------
* categorize_score(score) -> 'detractor' | 'passive' | 'promoter'
* calculate_nps(scores) -> int in range(-100, 100)
* should_trigger_nps(last_triggered_at, survey_type, first_paid_at, plan) -> bool
##
DB helpers (async)
------------------
* create_survey(db, org_id, user_id, survey_type) -> NpsSurvey
* submit_response(db, survey_id, score, comment) -> NpsSurvey
* get_pending_survey(db, org_id, user_id) -> NpsSurvey | None
* get_org_nps(db, org_id, days=90) -> dict with promoters, passives, detractors, nps_score
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.nps import NpsSurvey
from app.services.audit import log_action

logger = logging.getLogger(__name__)

NpsCategory = Literal["promoter", "passive", "detractor"]


# ── Pure helpers ───────────────────────────────────────────────────────────────

def categorize_score(score: int) -> str:
    """Classify an NPS score as detractor, passive, or promoter.

    Raises ValueError if score is outside [0, 10].
    """
    if score < 0 or score > 10:
        raise ValueError(f"NPS score must be 0-10, got {score}")
    if score <= 6:
        return "detractor"
    if score <= 8:
        return "passive"
    return "promoter"


def calculate_nps(scores: list[int]) -> int:
    """Calculate net promoter score from a list of 0-10 scores.

    Returns 0 for an empty list. Result is clamped to [-100, 100].
    """
    if not scores:
        return 0
    total = len(scores)
    promoters = sum(1 for s in scores if s >= 9)
    detractors = sum(1 for s in scores if s <= 6)
    pct_promoters = promoters / total * 100
    pct_detractors = detractors / total * 100
    nps = round(pct_promoters - pct_detractors)
    return max(-100, min(100, nps))


def should_trigger_nps(
    last_triggered_at: Optional[datetime] = None,
    survey_type: str = "",
    first_paid_at: Optional[datetime] = None,
    plan: str = "starter",
    *,
    now: Optional[datetime] = None,
) -> bool:
    """Determine whether to trigger an NPS survey for a given type.

    Args:
        last_triggered_at: When the last NPS was triggered for this org/user.
        survey_type: One of "day_30", "day_90", "cancellation", "quarterly".
        first_paid_at: When the org first paid (UTC).
        plan: Org subscription plan.
        now: Override current UTC time (for testing).

    Returns False for unknown types.
    """
    _now = now if now is not None else datetime.now(timezone.utc)

    # Minimum days between consecutive non-cancellation surveys
    _MIN_RETRIGGER_DAYS = 14

    if survey_type == NpsSurvey.TYPE_CANCELLATION:
        return True

    # Recency guard (not applied to cancellation)
    if last_triggered_at is not None and survey_type != NpsSurvey.TYPE_QUARTERLY:
        if (_now - last_triggered_at).days < _MIN_RETRIGGER_DAYS:
            return False

    if survey_type == NpsSurvey.TYPE_DAY_30:
        if first_paid_at is None:
            return False
        days_since = (_now - first_paid_at).days
        return 28 <= days_since <= 32

    if survey_type == NpsSurvey.TYPE_DAY_90:
        if first_paid_at is None:
            return False
        days_since = (_now - first_paid_at).days
        return 88 <= days_since <= 92

    if survey_type == NpsSurvey.TYPE_QUARTERLY:
        if plan != "enterprise":
            return False
        if last_triggered_at is None:
            return True
        return (_now - last_triggered_at).days > 90

    return False


# ── DB helpers ─────────────────────────────────────────────────────────────────

async def create_survey(
    db: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    survey_type: str,
) -> NpsSurvey:
    """Insert a new NpsSurvey row, commit, and return it."""
    try:
        survey = NpsSurvey(
            org_id=org_id,
            user_id=user_id,
            survey_type=survey_type,
            followup_status=NpsSurvey.FOLLOWUP_NONE,
        )
        db.add(survey)
        await db.commit()
        await db.refresh(survey)
        await log_action(
            db,
            action="nps.triggered",
            org_id=org_id,
            target_type="nps_survey",
            target_id=str(survey.id),
            metadata={"survey_type": survey_type, "user_id": str(user_id)},
        )
        await db.commit()
        return survey
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_survey failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


async def submit_response(
    db: AsyncSession,
    survey_id: uuid.UUID,
    score: int,
    comment: Optional[str] = None,
) -> NpsSurvey:
    """Record the respondent's score and comment on an existing survey."""
    try:
        if score < 0 or score > 10:
            raise HTTPException(status_code=422, detail="Score must be between 0 and 10")

        survey = await db.scalar(
            select(NpsSurvey).where(NpsSurvey.id == survey_id)
        )
        if not survey:
            raise HTTPException(status_code=404, detail="Survey not found")

        now = datetime.now(timezone.utc)
        survey.score = score
        survey.comment = comment
        survey.responded_at = now
        survey.response_time_seconds = int((now - survey.triggered_at).total_seconds())

        if score <= 6:
            survey.followup_status = NpsSurvey.FOLLOWUP_CSM

        await db.commit()
        await db.refresh(survey)
        await log_action(
            db,
            action="nps.responded",
            org_id=survey.org_id,
            target_type="nps_survey",
            target_id=str(survey.id),
            metadata={"score": score},
        )
        await db.commit()
        return survey
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"submit_response failed: {e}", extra={"survey_id": str(survey_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


async def get_pending_survey(
    db: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Optional[NpsSurvey]:
    """Return the newest unanswered survey for a user, or None."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        survey = await db.scalar(
            select(NpsSurvey)
            .where(
                NpsSurvey.org_id == org_id,
                NpsSurvey.user_id == user_id,
                NpsSurvey.responded_at.is_(None),
                NpsSurvey.triggered_at > cutoff,
            )
            .order_by(NpsSurvey.triggered_at.desc())
            .limit(1)
        )
        return survey
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_pending_survey failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


async def get_org_nps(
    db: AsyncSession,
    org_id: uuid.UUID,
    days: int = 90,
) -> dict:
    """Return NPS breakdown for an org over the last `days` days."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (await db.execute(
            select(NpsSurvey.score)
            .where(
                NpsSurvey.org_id == org_id,
                NpsSurvey.responded_at.is_not(None),
                NpsSurvey.responded_at >= cutoff,
                NpsSurvey.score.is_not(None),
            )
        )).scalars().all()

        scores = [s for s in rows if s is not None]
        total = len(scores)
        promoters = sum(1 for s in scores if s >= 9)
        passives = sum(1 for s in scores if 7 <= s <= 8)
        detractors = sum(1 for s in scores if s <= 6)
        nps_score = calculate_nps(scores)

        return {
            "promoters": promoters,
            "passives": passives,
            "detractors": detractors,
            "total": total,
            "nps_score": nps_score,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_org_nps failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
