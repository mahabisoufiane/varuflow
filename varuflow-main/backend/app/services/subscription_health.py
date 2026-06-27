"""Subscription health scoring service.

Calculates a 0–100 health score for a Varuflow organization based on
weighted signals. Scores are stored in subscription_health_scores and used
to trigger proactive retention interventions.

Score bands
-----------
80–100  healthy
50–79   at_risk
0–49    critical
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.marketing.nps_models import SubscriptionHealthScore
from app.services.audit import log_action

logger = logging.getLogger(__name__)


@dataclass
class HealthFactors:
    logins_last_7d: int = 0           # weight +20, normalized to max 7
    logins_last_30d: int = 0          # weight +15, normalized to max 30
    feature_diversity: int = 0        # 0-10 (distinct feature areas used) weight +15
    approaching_limits: bool = False   # weight -10
    failed_payments: int = 0          # weight -20 per failed payment (cap at -40)
    support_sentiment: float = 0.0    # -1.0 to +1.0 (weight effect: +10 * sentiment)
    last_nps_score: Optional[int] = None  # weight +15 if set (normalized to 0-1)
    onboarding_complete: bool = False      # weight +10
    days_since_last_invoice: int = 999    # weight -10 if > 30 days


def calculate_health_score(factors: HealthFactors) -> tuple[int, str]:
    """Return (score 0-100, risk_level) based on weighted factors."""
    score: float = 35.0

    # Positive signals
    score += 20.0 * min(factors.logins_last_7d, 7) / 7
    score += 15.0 * min(factors.logins_last_30d, 30) / 30
    score += 15.0 * min(factors.feature_diversity, 10) / 10

    # Negative signals
    if factors.approaching_limits:
        score -= 10.0
    score -= min(20.0 * factors.failed_payments, 40.0)

    # Sentiment: +10 * sentiment (can be negative)
    score += 10.0 * factors.support_sentiment

    # NPS: normalize 0-10 to 0-1
    if factors.last_nps_score is not None:
        score += 15.0 * factors.last_nps_score / 10

    if factors.onboarding_complete:
        score += 10.0

    if factors.days_since_last_invoice > 30:
        score -= 10.0

    final = max(0, min(100, round(score)))

    if final >= 80:
        risk_level = SubscriptionHealthScore.RISK_HEALTHY
    elif final >= 50:
        risk_level = SubscriptionHealthScore.RISK_AT_RISK
    else:
        risk_level = SubscriptionHealthScore.RISK_CRITICAL

    return final, risk_level


# ── DB helpers ─────────────────────────────────────────────────────────────────

async def save_health_score(
    db: AsyncSession,
    org_id: uuid.UUID,
    factors: HealthFactors,
) -> SubscriptionHealthScore:
    """Calculate score and insert a new row for the org. Returns the new row."""
    try:
        score_val, risk_level = calculate_health_score(factors)
        factors_dict = {
            "logins_last_7d": factors.logins_last_7d,
            "logins_last_30d": factors.logins_last_30d,
            "feature_diversity": factors.feature_diversity,
            "approaching_limits": factors.approaching_limits,
            "failed_payments": factors.failed_payments,
            "support_sentiment": factors.support_sentiment,
            "last_nps_score": factors.last_nps_score,
            "onboarding_complete": factors.onboarding_complete,
            "days_since_last_invoice": factors.days_since_last_invoice,
        }
        row = SubscriptionHealthScore(
            org_id=org_id,
            score=score_val,
            risk_level=risk_level,
            factors=factors_dict,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        await log_action(
            db,
            action="health.calculated",
            org_id=org_id,
            target_type="subscription_health_score",
            target_id=str(row.id),
            metadata={"score": score_val, "risk_level": risk_level},
        )
        await db.commit()
        return row
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"save_health_score failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


async def get_latest_score(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> Optional[SubscriptionHealthScore]:
    """Return the most recent health score row for an org, or None."""
    try:
        row = await db.scalar(
            select(SubscriptionHealthScore)
            .where(SubscriptionHealthScore.org_id == org_id)
            .order_by(SubscriptionHealthScore.calculated_at.desc())
            .limit(1)
        )
        return row
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_latest_score failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


async def get_all_scores(
    db: AsyncSession,
    risk_level: Optional[str] = None,
) -> list[SubscriptionHealthScore]:
    """Return all health score rows, optionally filtered by risk_level."""
    try:
        q = select(SubscriptionHealthScore).order_by(
            SubscriptionHealthScore.calculated_at.desc()
        )
        if risk_level is not None:
            q = q.where(SubscriptionHealthScore.risk_level == risk_level)
        rows = (await db.execute(q)).scalars().all()
        return list(rows)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_all_scores failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def mark_intervention(
    db: AsyncSession,
    score_id: uuid.UUID,
) -> SubscriptionHealthScore:
    """Set intervention_triggered_at = now() on a health score row."""
    try:
        row = await db.scalar(
            select(SubscriptionHealthScore).where(SubscriptionHealthScore.id == score_id)
        )
        if not row:
            raise HTTPException(status_code=404, detail="Health score not found")

        row.intervention_triggered_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(row)
        await log_action(
            db,
            action="health.intervention_triggered",
            org_id=row.org_id,
            target_type="subscription_health_score",
            target_id=str(row.id),
            metadata={"risk_level": row.risk_level, "score": row.score},
        )
        await db.commit()
        return row
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"mark_intervention failed: {e}", extra={"score_id": str(score_id)}
        )
        raise HTTPException(status_code=500, detail="Internal server error")
