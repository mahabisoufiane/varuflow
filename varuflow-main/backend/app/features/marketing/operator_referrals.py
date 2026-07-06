"""Router for operator-to-operator referrals.

Member endpoints (auth required):
  POST /api/referrals/generate   — generate or return existing referral link
  GET  /api/referrals/me         — list referrals + earnings summary

Public endpoints (no auth):
  POST /api/referrals/track-click — record a link click
  POST /api/referrals/redeem      — associate a new org with a referral code
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.operator_referrals import OperatorReferral
from app.services.audit import log_action
from app.services.partner_commissions import generate_operator_referral_code
from app.middleware.plan_check import require_module

log = logging.getLogger(__name__)

router = APIRouter(tags=["operator-referrals"], dependencies=[Depends(require_module("crm"))])

_DAILY_GENERATE_LIMIT = 50


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class GenerateIn(BaseModel):
    reward_type: str = "commission"  # commission | free_month


class TrackClickIn(BaseModel):
    code: str


class RedeemIn(BaseModel):
    code: str
    new_org_id: str


# ---------------------------------------------------------------------------
# Response helper
# ---------------------------------------------------------------------------


def _referral_dict(r: OperatorReferral) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "referrer_org_id": str(r.referrer_org_id),
        "referee_org_id": str(r.referee_org_id) if r.referee_org_id else None,
        "referral_code": r.referral_code,
        "referral_method": r.referral_method,
        "reward_type": r.reward_type,
        "commission_rate_pct": float(r.commission_rate_pct),
        "status": r.status,
        "clicked_at": r.clicked_at.isoformat() if r.clicked_at else None,
        "signed_up_at": r.signed_up_at.isoformat() if r.signed_up_at else None,
        "converted_at": r.converted_at.isoformat() if r.converted_at else None,
        "paid_out_at": r.paid_out_at.isoformat() if r.paid_out_at else None,
        "months_remaining": r.months_remaining,
        "subscription_amount": float(r.subscription_amount) if r.subscription_amount is not None else None,
        "commission_amount": float(r.commission_amount) if r.commission_amount is not None else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ---------------------------------------------------------------------------
# Member endpoints
# ---------------------------------------------------------------------------


@router.post("/api/referrals/generate")
async def generate_referral(
    body: GenerateIn,
    db: AsyncSession = Depends(get_db),
    member: dict = Depends(get_current_member),
) -> dict[str, Any]:
    """Generate (or return an existing) referral link for the caller's org.

    Idempotent: if the org already has a referral with the same reward_type
    that was created today, it is returned without creating a new one.
    Rate-limited to 50 new referrals per org per calendar day (UTC).
    """
    try:
        org_id = member["org_id"]
        user_id = uuid.UUID(str(member["user_id"]))
        org_name: str = member.get("org_name", "ORG")

        # Idempotency: return if an active (non-expired) referral already exists
        existing_result = await db.execute(
            select(OperatorReferral).where(
                OperatorReferral.referrer_org_id == org_id,
                OperatorReferral.reward_type == body.reward_type,
                OperatorReferral.status != OperatorReferral.STATUS_EXPIRED,
            ).limit(1)
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            referral_url = f"{settings.FRONTEND_URL}/signup?ref={existing.referral_code}"
            return {
                "referral_code": existing.referral_code,
                "referral_url": referral_url,
                "reward_type": existing.reward_type,
                "commission_rate_pct": float(existing.commission_rate_pct),
            }

        # Rate limit: max 50 new referrals created by this org today (UTC midnight)
        today_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        count_result = await db.execute(
            select(func.count()).select_from(OperatorReferral).where(
                OperatorReferral.referrer_org_id == org_id,
                OperatorReferral.created_at >= today_utc,
            )
        )
        daily_count = count_result.scalar() or 0
        if daily_count >= _DAILY_GENERATE_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Daily referral generation limit reached (50/day)",
            )

        # Generate a unique code
        for _ in range(5):
            code = generate_operator_referral_code(org_name)
            dupe = await db.execute(
                select(OperatorReferral).where(OperatorReferral.referral_code == code)
            )
            if dupe.scalar_one_or_none() is None:
                break
        else:
            raise HTTPException(status_code=500, detail="Failed to generate unique referral code")

        referral = OperatorReferral(
            referrer_org_id=org_id,
            referrer_user_id=user_id,
            referral_code=code,
            reward_type=body.reward_type,
            status=OperatorReferral.STATUS_PENDING,
        )
        db.add(referral)
        await db.flush()

        await log_action(
            db=db,
            action="referral.generated",
            resource_type="operator_referral",
            resource_id=str(referral.id),
            org_id=str(org_id),
            user_id=str(user_id),
            metadata={"reward_type": body.reward_type, "code": code},
        )
        await db.commit()

        referral_url = f"{settings.FRONTEND_URL}/signup?ref={code}"
        log.info("referral.generated: org=%s code=%s", org_id, code)
        return {
            "referral_code": code,
            "referral_url": referral_url,
            "reward_type": referral.reward_type,
            "commission_rate_pct": float(referral.commission_rate_pct),
        }
    except HTTPException:
        raise
    except Exception as exc:
        log.error("generate_referral failed: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/referrals/me")
async def list_my_referrals(
    db: AsyncSession = Depends(get_db),
    member: dict = Depends(get_current_member),
) -> dict[str, Any]:
    """List all referrals for the caller's org plus an earnings summary."""
    try:
        org_id = member["org_id"]
        result = await db.execute(
            select(OperatorReferral)
            .where(OperatorReferral.referrer_org_id == org_id)
            .order_by(OperatorReferral.created_at.desc())
        )
        referrals = result.scalars().all()

        total_earned = sum(
            r.commission_amount for r in referrals if r.commission_amount is not None
        )
        pending_amount = sum(
            r.commission_amount
            for r in referrals
            if r.status == OperatorReferral.STATUS_CONVERTED and r.commission_amount is not None
        )
        paid_out_amount = sum(
            r.commission_amount
            for r in referrals
            if r.status == OperatorReferral.STATUS_PAID_OUT and r.commission_amount is not None
        )

        return {
            "referrals": [_referral_dict(r) for r in referrals],
            "summary": {
                "total_earned": float(total_earned),
                "pending": float(pending_amount),
                "paid_out": float(paid_out_amount),
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        log.error("list_my_referrals failed: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------


@router.post("/api/referrals/track-click")
async def track_referral_click(
    body: TrackClickIn,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Record a click on a referral link. Sets clicked_at on first call only."""
    try:
        result = await db.execute(
            select(OperatorReferral).where(OperatorReferral.referral_code == body.code)
        )
        referral = result.scalar_one_or_none()
        if referral is None:
            raise HTTPException(status_code=404, detail="Referral code not found")

        if referral.clicked_at is None:
            referral.clicked_at = datetime.now(timezone.utc)
            await db.commit()

        return {"referral_code": referral.referral_code, "reward_type": referral.reward_type}
    except HTTPException:
        raise
    except Exception as exc:
        log.error("track_referral_click failed: code=%s error=%s", body.code, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/referrals/redeem")
async def redeem_referral(
    body: RedeemIn,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Associate a newly-registered org with a referral code.

    Prevents self-referrals. Sets referee_org_id, signed_up_at, and
    status='signed_up'. Audit-logs the event.
    """
    try:
        result = await db.execute(
            select(OperatorReferral).where(OperatorReferral.referral_code == body.code)
        )
        referral = result.scalar_one_or_none()
        if referral is None:
            raise HTTPException(status_code=404, detail="Referral code not found")

        # Prevent self-referral
        if str(referral.referrer_org_id) == str(body.new_org_id):
            raise HTTPException(status_code=400, detail="Self-referral not allowed")

        referral.referee_org_id = uuid.UUID(body.new_org_id)
        referral.signed_up_at = datetime.now(timezone.utc)
        referral.status = OperatorReferral.STATUS_SIGNED_UP

        await db.flush()
        await log_action(
            db=db,
            action="referral.redeemed",
            resource_type="operator_referral",
            resource_id=str(referral.id),
            metadata={"new_org_id": body.new_org_id, "code": body.code},
        )
        await db.commit()
        log.info("referral.redeemed: code=%s new_org=%s", body.code, body.new_org_id)
        return _referral_dict(referral)
    except HTTPException:
        raise
    except Exception as exc:
        log.error("redeem_referral failed: code=%s error=%s", body.code, exc)
        raise HTTPException(status_code=500, detail="Internal server error")
