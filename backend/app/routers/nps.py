"""NPS triggered surveys and subscription health — member + admin endpoints.

Member endpoints
----------------
GET  /api/nps/pending          — return pending survey for current user or {"survey": null}
POST /api/nps/respond          — submit score + comment
POST /api/nps/dismiss          — dismiss without responding
GET  /api/nps/stats            — NPS breakdown for org (last 90 days)

Admin endpoints
---------------
GET  /api/admin/nps/all                      — list all surveys (filterable)
GET  /api/admin/health                       — list health scores (filterable)
POST /api/admin/health/{id}/intervene        — mark intervention triggered
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.nps import NpsSurvey, SubscriptionHealthScore
from app.services.email import send_nps_detractor_followup_email
from app.services.nps import (
    categorize_score,
    get_org_nps,
    get_pending_survey,
    submit_response as svc_submit_response,
)
from app.services.subscription_health import get_all_scores, mark_intervention

router = APIRouter(tags=["nps"])
log = logging.getLogger(__name__)


# ── Admin auth dependency ──────────────────────────────────────────────────────

async def _require_admin(
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
) -> None:
    key = getattr(settings, "ADMIN_API_KEY", "") or ""
    if not key:
        raise HTTPException(status_code=503, detail="Admin API not configured")
    if not x_admin_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin key")
    import secrets
    if not secrets.compare_digest(x_admin_key, key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin key")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _survey_out(s: NpsSurvey) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "org_id": str(s.org_id),
        "user_id": str(s.user_id),
        "score": s.score,
        "comment": s.comment,
        "survey_type": s.survey_type,
        "triggered_at": s.triggered_at.isoformat(),
        "responded_at": s.responded_at.isoformat() if s.responded_at else None,
        "response_time_seconds": s.response_time_seconds,
        "followup_status": s.followup_status,
    }


def _health_out(h: SubscriptionHealthScore) -> dict[str, Any]:
    return {
        "id": str(h.id),
        "org_id": str(h.org_id),
        "score": h.score,
        "risk_level": h.risk_level,
        "factors": h.factors,
        "calculated_at": h.calculated_at.isoformat(),
        "intervention_triggered_at": (
            h.intervention_triggered_at.isoformat()
            if h.intervention_triggered_at else None
        ),
    }


_FOLLOWUP_ACTION = {
    "promoter": "review",
    "passive": "improve",
    "detractor": "call",
}


# ── Schemas ────────────────────────────────────────────────────────────────────

class RespondIn(BaseModel):
    survey_id: str
    score: int = Field(ge=0, le=10)
    comment: Optional[str] = None


class DismissIn(BaseModel):
    survey_id: str


# ── Member endpoints ───────────────────────────────────────────────────────────

@router.get("/api/nps/pending")
async def get_pending(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _, member = ctx
    org_id = member["org_id"]
    user_id = member["user_id"]
    try:
        survey = await get_pending_survey(db, org_id=org_id, user_id=user_id)
        if survey is None:
            return {"survey": None}
        return {"survey": _survey_out(survey)}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"get_pending failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/nps/respond")
async def respond(
    body: RespondIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _, member = ctx
    org_id = member["org_id"]
    try:
        survey_id = uuid.UUID(body.survey_id)
        survey = await svc_submit_response(
            db, survey_id=survey_id, score=body.score, comment=body.comment
        )
        category = categorize_score(body.score)

        # Fire detractor follow-up email immediately after a 0-6 score
        if category == "detractor":
            try:
                # Get the org's notification email for the follow-up
                from app.models.organization import Organization
                org = await db.get(Organization, org_id)
                org_email = None
                try:
                    from app.models.auth import AuthUser
                    from app.models.organization import OrganizationMember, OrgRole
                    row = await db.execute(
                        select(AuthUser.email)
                        .join(OrganizationMember, OrganizationMember.user_id == AuthUser.id)
                        .where(
                            OrganizationMember.org_id == org_id,
                            OrganizationMember.role == OrgRole.OWNER,
                        )
                        .limit(1)
                    )
                    org_email = row.scalar_one_or_none()
                except Exception:
                    pass
                if org_email:
                    org_name = getattr(org, "name", str(org_id)) if org else str(org_id)
                    calendly_url = getattr(settings, "CALENDLY_DETRACTOR_URL", "https://calendly.com/varuflow/feedback")
                    await send_nps_detractor_followup_email(
                        to_email=org_email,
                        org_name=org_name,
                        score=body.score,
                        comment=body.comment,
                        calendly_url=calendly_url,
                    )
            except Exception as email_err:
                log.warning(f"detractor_followup_email failed (non-fatal): {email_err}")

        return {
            "survey": _survey_out(survey),
            "category": category,
            "followup_action": _FOLLOWUP_ACTION.get(category, "improve"),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"respond failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/nps/dismiss")
async def dismiss(
    body: DismissIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _, member = ctx
    org_id = member["org_id"]
    try:
        survey_id = uuid.UUID(body.survey_id)
        survey = await db.scalar(
            select(NpsSurvey).where(
                NpsSurvey.id == survey_id,
                NpsSurvey.org_id == org_id,
            )
        )
        if not survey:
            raise HTTPException(status_code=404, detail="Survey not found")
        survey.responded_at = datetime.now(timezone.utc)
        # score stays None to mark a dismiss (no score given)
        await db.commit()
        await db.refresh(survey)
        return {"survey": _survey_out(survey)}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"dismiss failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/nps/stats")
async def nps_stats(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _, member = ctx
    org_id = member["org_id"]
    try:
        stats = await get_org_nps(db, org_id=org_id)
        return stats
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"nps_stats failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Admin endpoints ────────────────────────────────────────────────────────────

@router.get("/api/admin/nps/all")
async def admin_list_surveys(
    org_id: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: None = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        q = select(NpsSurvey).order_by(NpsSurvey.triggered_at.desc())
        if org_id:
            q = q.where(NpsSurvey.org_id == uuid.UUID(org_id))
        if type:
            q = q.where(NpsSurvey.survey_type == type)
        rows = (await db.execute(q.offset(offset).limit(limit))).scalars().all()
        return {
            "limit": limit,
            "offset": offset,
            "items": [_survey_out(s) for s in rows],
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"admin_list_surveys failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/admin/health")
async def admin_list_health(
    risk_level: Optional[str] = Query(default=None),
    _: None = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    try:
        rows = await get_all_scores(db, risk_level=risk_level)
        return [_health_out(h) for h in rows]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"admin_list_health failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/admin/health/{score_id}/intervene")
async def admin_intervene(
    score_id: uuid.UUID,
    _: None = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        row = await mark_intervention(db, score_id=score_id)
        return _health_out(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"admin_intervene failed: {e}", extra={"score_id": str(score_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
