"""Router for the accounting firm partner programme.

Public endpoints:
  POST /api/partners/apply         — submit a partner application (no auth)

Admin endpoints (x-admin-key required):
  GET  /api/admin/partners          — list all partners
  GET  /api/admin/partners/{id}     — single partner + referrals
  POST /api/admin/partners/{id}/approve
  POST /api/admin/partners/{id}/reject

Partner self-service (member auth):
  GET  /api/partners/me             — dashboard stats
  GET  /api/partners/me/referrals   — all referrals
  GET  /api/partners/me/commissions — referrals with commission data
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.accounting_partners import AccountingFirmPartner, AccountingPartnerReferral
from app.services.audit import log_action
from app.services.partner_commissions import generate_partner_code

log = logging.getLogger(__name__)

router = APIRouter(tags=["accounting-partners"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class PartnerApplicationIn(BaseModel):
    firm_name: str
    contact_name: str
    contact_email: EmailStr
    contact_phone: str | None = None
    country: str = "SE"
    city: str | None = None
    website: str | None = None
    client_count_estimate: int | None = None
    application_notes: str | None = None


class PartnerApproveIn(BaseModel):
    commission_rate_pct: float = 25.0


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


async def _assert_admin(request: Request) -> None:
    """Raise 403 unless the request carries the correct admin API key."""
    key = request.headers.get("x-admin-key", "")
    if key and key == settings.ADMIN_API_KEY:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _partner_dict(p: AccountingFirmPartner) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "firm_name": p.firm_name,
        "contact_name": p.contact_name,
        "contact_email": p.contact_email,
        "contact_phone": p.contact_phone,
        "country": p.country,
        "city": p.city,
        "website": p.website,
        "referral_code": p.referral_code,
        "commission_rate_pct": float(p.commission_rate_pct),
        "status": p.status,
        "approved_at": p.approved_at.isoformat() if p.approved_at else None,
        "vat_number": p.vat_number,
        "business_registration_number": p.business_registration_number,
        "client_count_estimate": p.client_count_estimate,
        "application_notes": p.application_notes,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _referral_dict(r: AccountingPartnerReferral) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "partner_id": str(r.partner_id),
        "referred_org_id": str(r.referred_org_id) if r.referred_org_id else None,
        "status": r.status,
        "clicked_at": r.clicked_at.isoformat() if r.clicked_at else None,
        "signed_up_at": r.signed_up_at.isoformat() if r.signed_up_at else None,
        "converted_at": r.converted_at.isoformat() if r.converted_at else None,
        "paid_out_at": r.paid_out_at.isoformat() if r.paid_out_at else None,
        "subscription_amount": float(r.subscription_amount) if r.subscription_amount is not None else None,
        "commission_amount": float(r.commission_amount) if r.commission_amount is not None else None,
        "months_remaining": r.months_remaining,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ---------------------------------------------------------------------------
# Public endpoint — partner application
# ---------------------------------------------------------------------------


@router.post("/api/partners/apply", status_code=status.HTTP_201_CREATED)
async def apply_as_partner(
    body: PartnerApplicationIn,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Submit an accounting firm partner application (no authentication required).

    Generates a unique referral code, creates the partner record with
    status='pending', and returns the id, referral_code, and status.
    """
    try:
        # Generate a collision-resistant code (retry once on the rare clash)
        for _ in range(5):
            code = generate_partner_code(body.firm_name)
            existing = await db.execute(
                select(AccountingFirmPartner).where(AccountingFirmPartner.referral_code == code)
            )
            if existing.scalar_one_or_none() is None:
                break
        else:
            raise HTTPException(status_code=500, detail="Failed to generate unique referral code")

        partner = AccountingFirmPartner(
            firm_name=body.firm_name,
            contact_name=body.contact_name,
            contact_email=body.contact_email,
            contact_phone=body.contact_phone,
            country=body.country,
            city=body.city,
            website=body.website,
            referral_code=code,
            client_count_estimate=body.client_count_estimate,
            application_notes=body.application_notes,
            status=AccountingFirmPartner.STATUS_PENDING,
        )
        db.add(partner)
        await db.flush()

        await log_action(
            db=db,
            action="partner.applied",
            resource_type="accounting_firm_partner",
            resource_id=str(partner.id),
            metadata={"firm_name": body.firm_name, "country": body.country},
        )
        await db.commit()
        await db.refresh(partner)
        log.info("partner.applied: id=%s firm=%s", partner.id, body.firm_name)
        return {"id": str(partner.id), "referral_code": partner.referral_code, "status": partner.status}
    except HTTPException:
        raise
    except Exception as exc:
        log.error("apply_as_partner failed: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@router.get("/api/admin/partners")
async def admin_list_partners(
    request: Request,
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List all accounting firm partners. Optionally filter by ?status=."""
    try:
        await _assert_admin(request)
        q = select(AccountingFirmPartner)
        if status_filter:
            q = q.where(AccountingFirmPartner.status == status_filter)
        q = q.order_by(AccountingFirmPartner.created_at.desc())
        result = await db.execute(q)
        partners = result.scalars().all()
        return [_partner_dict(p) for p in partners]
    except HTTPException:
        raise
    except Exception as exc:
        log.error("admin_list_partners failed: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/admin/partners/{partner_id}")
async def admin_get_partner(
    partner_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return a single partner record together with its referral list."""
    try:
        await _assert_admin(request)
        result = await db.execute(
            select(AccountingFirmPartner).where(AccountingFirmPartner.id == partner_id)
        )
        partner = result.scalar_one_or_none()
        if partner is None:
            raise HTTPException(status_code=404, detail="Partner not found")

        ref_result = await db.execute(
            select(AccountingPartnerReferral).where(
                AccountingPartnerReferral.partner_id == partner_id
            ).order_by(AccountingPartnerReferral.created_at.desc())
        )
        referrals = ref_result.scalars().all()

        data = _partner_dict(partner)
        data["referrals"] = [_referral_dict(r) for r in referrals]
        return data
    except HTTPException:
        raise
    except Exception as exc:
        log.error("admin_get_partner failed: partner_id=%s error=%s", partner_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/admin/partners/{partner_id}/approve")
async def admin_approve_partner(
    partner_id: uuid.UUID,
    body: PartnerApproveIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    member: dict = Depends(get_current_member),
) -> dict[str, Any]:
    """Approve a pending partner application (requires admin key + member auth)."""
    try:
        await _assert_admin(request)
        result = await db.execute(
            select(AccountingFirmPartner).where(AccountingFirmPartner.id == partner_id)
        )
        partner = result.scalar_one_or_none()
        if partner is None:
            raise HTTPException(status_code=404, detail="Partner not found")

        partner.status = AccountingFirmPartner.STATUS_APPROVED
        partner.approved_at = datetime.now(timezone.utc)
        partner.approved_by_user_id = uuid.UUID(member["user_id"])
        partner.commission_rate_pct = body.commission_rate_pct

        await db.flush()
        await log_action(
            db=db,
            action="partner.approved",
            resource_type="accounting_firm_partner",
            resource_id=str(partner_id),
            metadata={
                "approved_by": member["user_id"],
                "commission_rate_pct": body.commission_rate_pct,
            },
        )
        await db.commit()
        await db.refresh(partner)
        return _partner_dict(partner)
    except HTTPException:
        raise
    except Exception as exc:
        log.error("admin_approve_partner failed: partner_id=%s error=%s", partner_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/admin/partners/{partner_id}/reject")
async def admin_reject_partner(
    partner_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Reject (terminate) a partner application."""
    try:
        await _assert_admin(request)
        result = await db.execute(
            select(AccountingFirmPartner).where(AccountingFirmPartner.id == partner_id)
        )
        partner = result.scalar_one_or_none()
        if partner is None:
            raise HTTPException(status_code=404, detail="Partner not found")

        partner.status = AccountingFirmPartner.STATUS_TERMINATED

        await db.flush()
        await log_action(
            db=db,
            action="partner.rejected",
            resource_type="accounting_firm_partner",
            resource_id=str(partner_id),
            metadata={},
        )
        await db.commit()
        await db.refresh(partner)
        return _partner_dict(partner)
    except HTTPException:
        raise
    except Exception as exc:
        log.error("admin_reject_partner failed: partner_id=%s error=%s", partner_id, exc)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Partner self-service endpoints (member auth)
# ---------------------------------------------------------------------------


async def _get_partner_for_member(
    db: AsyncSession, member: dict
) -> AccountingFirmPartner:
    """Look up the AccountingFirmPartner whose contact_email matches the member."""
    member_email = member["email"]
    result = await db.execute(select(AccountingFirmPartner))
    all_partners = result.scalars().all()
    for p in all_partners:
        if p.contact_email == member_email:
            return p
    raise HTTPException(status_code=404, detail="No partner record found for this account")


@router.get("/api/partners/me")
async def partner_me(
    db: AsyncSession = Depends(get_db),
    member: dict = Depends(get_current_member),
) -> dict[str, Any]:
    """Return the authenticated member's partner dashboard stats."""
    try:
        partner = await _get_partner_for_member(db, member)

        ref_result = await db.execute(
            select(AccountingPartnerReferral).where(
                AccountingPartnerReferral.partner_id == partner.id
            )
        )
        referrals = ref_result.scalars().all()

        total_referrals = len(referrals)
        converted = sum(1 for r in referrals if r.status in (
            AccountingPartnerReferral.STATUS_CONVERTED,
            AccountingPartnerReferral.STATUS_PAID_OUT,
        ))
        total_earned = sum(
            r.commission_amount for r in referrals if r.commission_amount is not None
        )

        data = _partner_dict(partner)
        data["stats"] = {
            "total_referrals": total_referrals,
            "converted": converted,
            "total_earned": float(total_earned),
        }
        return data
    except HTTPException:
        raise
    except Exception as exc:
        log.error("partner_me failed: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/partners/me/referrals")
async def partner_me_referrals(
    db: AsyncSession = Depends(get_db),
    member: dict = Depends(get_current_member),
) -> list[dict[str, Any]]:
    """Return all referrals for the authenticated partner."""
    try:
        partner = await _get_partner_for_member(db, member)
        result = await db.execute(
            select(AccountingPartnerReferral)
            .where(AccountingPartnerReferral.partner_id == partner.id)
            .order_by(AccountingPartnerReferral.created_at.desc())
        )
        referrals = result.scalars().all()
        return [_referral_dict(r) for r in referrals]
    except HTTPException:
        raise
    except Exception as exc:
        log.error("partner_me_referrals failed: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/partners/me/commissions")
async def partner_me_commissions(
    db: AsyncSession = Depends(get_db),
    member: dict = Depends(get_current_member),
) -> list[dict[str, Any]]:
    """Return referrals with commission data for the authenticated partner."""
    try:
        partner = await _get_partner_for_member(db, member)
        result = await db.execute(
            select(AccountingPartnerReferral)
            .where(
                AccountingPartnerReferral.partner_id == partner.id,
                AccountingPartnerReferral.commission_amount.isnot(None),
            )
            .order_by(AccountingPartnerReferral.converted_at.desc())
        )
        referrals = result.scalars().all()
        return [_referral_dict(r) for r in referrals]
    except HTTPException:
        raise
    except Exception as exc:
        log.error("partner_me_commissions failed: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")
