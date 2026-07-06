"""14-day PRO trial: start, extend, status, convert."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.features.auth.organization import OrgRole, Organization
from app.services import trial_service as svc
from app.services.audit import log_action
from app.services.email import (
    send_trial_started_email,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/trial", tags=["trial"])


# ── Helpers ───────────────────────────────────────────────────────────────────


def _ids(ctx: tuple) -> tuple[uuid.UUID, uuid.UUID]:
    user_info, member = ctx
    uid = user_info.get("user_id") or user_info.get("sub")
    return member.org_id, uid if isinstance(uid, uuid.UUID) else uuid.UUID(str(uid))


async def _get_org(org_id: uuid.UUID, db: AsyncSession) -> Organization:
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


# ── Schemas ───────────────────────────────────────────────────────────────────


class TrialStartRequest(BaseModel):
    plan: str = Field(default="PRO", max_length=20)
    source: str = Field(default="signup", max_length=50)


class TrialStatusResponse(BaseModel):
    is_active: bool
    trial_plan: str | None
    trial_started_at: datetime | None
    trial_ends_at: datetime | None
    trial_converted_at: datetime | None
    trial_extended_count: int
    trial_source: str | None
    days_remaining: int
    can_extend: bool


class TrialExtendResponse(BaseModel):
    trial_ends_at: datetime
    trial_extended_count: int


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/start", status_code=status.HTTP_201_CREATED)
async def start_trial(
    body: TrialStartRequest,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> TrialStatusResponse:
    _, member = ctx
    if member.role != OrgRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "OWNER_REQUIRED", "message": "Only the org owner can start a trial."},
        )
    org_id, user_id = _ids(ctx)
    try:
        org = await _get_org(org_id, db)
        now = datetime.now(timezone.utc)
        svc.start_trial(org, plan=body.plan, source=body.source, now=now)
        await db.flush()
        await log_action(
            db,
            action="trial.started",
            org_id=org_id,
            actor_user_id=user_id,
            target_type="organization",
            target_id=str(org_id),
            request=request,
            extra={"plan": body.plan, "source": body.source},
        )
        await db.commit()
        await db.refresh(org)
        # fire-and-forget — do not block the response on email failure
        try:
            await send_trial_started_email(
                to_email=request.state.user_email if hasattr(request.state, "user_email") else None,
                org_name=org.name,
                plan=body.plan,
                trial_ends_at=org.trial_ends_at,
            )
        except Exception:  # noqa: BLE001
            pass
        return _to_status(org, now)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": str(exc), "message": str(exc).replace("_", " ")},
        )
    except HTTPException:
        raise
    except Exception as exc:
        log.error("start_trial failed: %s", str(exc), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/extend")
async def extend_trial(
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> TrialExtendResponse:
    _, member = ctx
    if member.role != OrgRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "OWNER_REQUIRED", "message": "Only the org owner can extend a trial."},
        )
    org_id, user_id = _ids(ctx)
    try:
        org = await _get_org(org_id, db)
        now = datetime.now(timezone.utc)
        await svc.extend_trial(org, db, now=now)
        await log_action(
            db,
            action="trial.extended",
            org_id=org_id,
            actor_user_id=user_id,
            target_type="organization",
            target_id=str(org_id),
            request=request,
            extra={"new_trial_ends_at": org.trial_ends_at.isoformat()},
        )
        await db.commit()
        await db.refresh(org)
        return TrialExtendResponse(
            trial_ends_at=org.trial_ends_at,
            trial_extended_count=org.trial_extended_count,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": str(exc), "message": str(exc).replace("_", " ")},
        )
    except HTTPException:
        raise
    except Exception as exc:
        log.error("extend_trial failed: %s", str(exc), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/status")
async def get_trial_status(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> TrialStatusResponse:
    org_id, _ = _ids(ctx)
    try:
        org = await _get_org(org_id, db)
        now = datetime.now(timezone.utc)
        return _to_status(org, now)
    except HTTPException:
        raise
    except Exception as exc:
        log.error("get_trial_status failed: %s", str(exc), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/convert")
async def convert_trial(
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> TrialStatusResponse:
    """
    Mark trial as paid. Typically called by the Stripe webhook handler after
    a successful subscription payment, forwarded here with the org's auth context.
    """
    org_id, user_id = _ids(ctx)
    try:
        org = await _get_org(org_id, db)
        now = datetime.now(timezone.utc)
        await svc.convert_trial(org, db, now=now)
        await log_action(
            db,
            action="trial.converted",
            org_id=org_id,
            actor_user_id=user_id,
            target_type="organization",
            target_id=str(org_id),
            request=request,
            extra={"trial_converted_at": now.isoformat()},
        )
        await db.commit()
        await db.refresh(org)
        return _to_status(org, now)
    except HTTPException:
        raise
    except Exception as exc:
        log.error("convert_trial failed: %s", str(exc), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Internal helper ───────────────────────────────────────────────────────────


def _to_status(org: Organization, now: datetime) -> TrialStatusResponse:
    return TrialStatusResponse(
        is_active=svc.is_trial_active(org, now),
        trial_plan=org.trial_plan,
        trial_started_at=org.trial_started_at,
        trial_ends_at=org.trial_ends_at,
        trial_converted_at=org.trial_converted_at,
        trial_extended_count=org.trial_extended_count,
        trial_source=org.trial_source,
        days_remaining=svc.days_remaining(org, now),
        can_extend=svc.can_extend(org),
    )
