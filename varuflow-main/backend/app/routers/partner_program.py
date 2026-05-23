"""Partner Program router — B2B affiliate/partner tracking."""
import logging
import random
import string
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.growth import Partner, PartnerDeal, PartnerProgram

logger = logging.getLogger(__name__)
router = APIRouter(tags=["partner-programs"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ProgramCreate(BaseModel):
    name: str
    description: str | None = None
    commission_type: str = "percentage"  # percentage | fixed
    commission_rate: float = 0.05
    min_deal_value: float | None = None
    payout_threshold: float = 500.0
    currency: str = "SEK"

class ProgramUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    commission_type: str | None = None
    commission_rate: float | None = None
    min_deal_value: float | None = None
    payout_threshold: float | None = None
    is_active: bool | None = None

class PartnerCreate(BaseModel):
    program_id: str | None = None
    company_name: str
    contact_name: str | None = None
    contact_email: str
    notes: str | None = None

class PartnerUpdate(BaseModel):
    program_id: str | None = None
    company_name: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    status: str | None = None
    notes: str | None = None

class DealCreate(BaseModel):
    partner_id: str
    customer_id: str | None = None
    invoice_id: str | None = None
    deal_name: str | None = None
    deal_value: float = 0.0
    notes: str | None = None

class DealStageUpdate(BaseModel):
    stage: str  # registered | approved | paid


def _gen_code(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


# ── Programs ──────────────────────────────────────────────────────────────────

@router.get("/api/growth/programs")
async def list_programs(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        rows = (await db.execute(
            select(PartnerProgram).where(PartnerProgram.org_id == org_id).order_by(PartnerProgram.created_at.desc())
        )).scalars().all()
        return [_prog_dict(p) for p in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_programs failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/growth/programs", status_code=201)
async def create_program(
    body: ProgramCreate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        prog = PartnerProgram(
            org_id=org_id,
            name=body.name,
            description=body.description,
            commission_type=body.commission_type,
            commission_rate=Decimal(str(body.commission_rate)),
            min_deal_value=Decimal(str(body.min_deal_value)) if body.min_deal_value else None,
            payout_threshold=Decimal(str(body.payout_threshold)),
            currency=body.currency,
        )
        db.add(prog)
        await db.commit()
        await db.refresh(prog)
        return _prog_dict(prog)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_program failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/growth/programs/{program_id}")
async def update_program(
    program_id: str,
    body: ProgramUpdate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        prog = (await db.execute(
            select(PartnerProgram).where(PartnerProgram.id == program_id, PartnerProgram.org_id == org_id)
        )).scalar_one_or_none()
        if not prog:
            raise HTTPException(status_code=404, detail="Program not found")
        for field, val in body.model_dump(exclude_none=True).items():
            if field in ("commission_rate", "min_deal_value", "payout_threshold") and val is not None:
                val = Decimal(str(val))
            setattr(prog, field, val)
        await db.commit()
        await db.refresh(prog)
        return _prog_dict(prog)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_program failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/growth/programs/{program_id}", status_code=204)
async def delete_program(
    program_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        prog = (await db.execute(
            select(PartnerProgram).where(PartnerProgram.id == program_id, PartnerProgram.org_id == org_id)
        )).scalar_one_or_none()
        if not prog:
            raise HTTPException(status_code=404, detail="Program not found")
        await db.delete(prog)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_program failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Partners ──────────────────────────────────────────────────────────────────

@router.get("/api/growth/partners")
async def list_partners(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        rows = (await db.execute(
            select(Partner).where(Partner.org_id == org_id).order_by(Partner.created_at.desc())
        )).scalars().all()
        return [_partner_dict(p) for p in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_partners failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/growth/partners", status_code=201)
async def create_partner(
    body: PartnerCreate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        # Generate unique referral code
        code = _gen_code()
        for _ in range(10):
            existing = (await db.execute(select(Partner).where(Partner.referral_code == code))).scalar_one_or_none()
            if not existing:
                break
            code = _gen_code()
        partner = Partner(
            org_id=org_id,
            program_id=body.program_id,
            company_name=body.company_name,
            contact_name=body.contact_name,
            contact_email=body.contact_email,
            referral_code=code,
            notes=body.notes,
        )
        db.add(partner)
        await db.commit()
        await db.refresh(partner)
        return _partner_dict(partner)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_partner failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/growth/partners/{partner_id}")
async def update_partner(
    partner_id: str,
    body: PartnerUpdate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        partner = (await db.execute(
            select(Partner).where(Partner.id == partner_id, Partner.org_id == org_id)
        )).scalar_one_or_none()
        if not partner:
            raise HTTPException(status_code=404, detail="Partner not found")
        for field, val in body.model_dump(exclude_none=True).items():
            setattr(partner, field, val)
        await db.commit()
        await db.refresh(partner)
        return _partner_dict(partner)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_partner failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/growth/partners/{partner_id}", status_code=204)
async def delete_partner(
    partner_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        partner = (await db.execute(
            select(Partner).where(Partner.id == partner_id, Partner.org_id == org_id)
        )).scalar_one_or_none()
        if not partner:
            raise HTTPException(status_code=404, detail="Partner not found")
        await db.delete(partner)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_partner failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Partner Deals ─────────────────────────────────────────────────────────────

@router.get("/api/growth/deals")
async def list_deals(
    partner_id: str | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(PartnerDeal).where(PartnerDeal.org_id == org_id)
        if partner_id:
            q = q.where(PartnerDeal.partner_id == partner_id)
        rows = (await db.execute(q.order_by(PartnerDeal.created_at.desc()))).scalars().all()
        return [_deal_dict(d) for d in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_deals failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/growth/deals", status_code=201)
async def create_deal(
    body: DealCreate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        # Verify partner belongs to org
        partner = (await db.execute(
            select(Partner).where(Partner.id == body.partner_id, Partner.org_id == org_id)
        )).scalar_one_or_none()
        if not partner:
            raise HTTPException(status_code=404, detail="Partner not found")

        # Compute commission
        program = partner.program
        if program and program.commission_type == "percentage":
            commission = Decimal(str(body.deal_value)) * program.commission_rate
        elif program and program.commission_type == "fixed":
            commission = program.commission_rate
        else:
            commission = Decimal("0")

        deal = PartnerDeal(
            org_id=org_id,
            partner_id=body.partner_id,
            customer_id=body.customer_id,
            invoice_id=body.invoice_id,
            deal_name=body.deal_name,
            deal_value=Decimal(str(body.deal_value)),
            commission_amount=commission,
            notes=body.notes,
        )
        db.add(deal)
        await db.commit()
        await db.refresh(deal)
        return _deal_dict(deal)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_deal failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/growth/deals/{deal_id}/stage")
async def update_deal_stage(
    deal_id: str,
    body: DealStageUpdate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        if body.stage not in ("registered", "approved", "paid"):
            raise HTTPException(status_code=422, detail="Invalid stage")
        deal = (await db.execute(
            select(PartnerDeal).where(PartnerDeal.id == deal_id, PartnerDeal.org_id == org_id)
        )).scalar_one_or_none()
        if not deal:
            raise HTTPException(status_code=404, detail="Deal not found")

        now = datetime.now(timezone.utc)
        deal.stage = body.stage
        if body.stage == "approved" and not deal.approved_at:
            deal.approved_at = now
            # Update partner totals
            partner = (await db.execute(select(Partner).where(Partner.id == deal.partner_id))).scalar_one_or_none()
            if partner:
                partner.total_referred_revenue = (partner.total_referred_revenue or Decimal("0")) + deal.deal_value
                partner.total_commission_earned = (partner.total_commission_earned or Decimal("0")) + deal.commission_amount
        elif body.stage == "paid" and not deal.paid_at:
            deal.paid_at = now
            partner = (await db.execute(select(Partner).where(Partner.id == deal.partner_id))).scalar_one_or_none()
            if partner:
                partner.total_commission_paid = (partner.total_commission_paid or Decimal("0")) + deal.commission_amount

        await db.commit()
        await db.refresh(deal)
        return _deal_dict(deal)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_deal_stage failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _prog_dict(p: PartnerProgram) -> dict:
    return {
        "id": str(p.id), "name": p.name, "description": p.description,
        "commission_type": p.commission_type, "commission_rate": float(p.commission_rate),
        "min_deal_value": float(p.min_deal_value) if p.min_deal_value else None,
        "payout_threshold": float(p.payout_threshold), "currency": p.currency,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }

def _partner_dict(p: Partner) -> dict:
    return {
        "id": str(p.id), "company_name": p.company_name,
        "contact_name": p.contact_name, "contact_email": p.contact_email,
        "referral_code": p.referral_code, "status": p.status,
        "program_id": str(p.program_id) if p.program_id else None,
        "total_referred_revenue": float(p.total_referred_revenue),
        "total_commission_earned": float(p.total_commission_earned),
        "total_commission_paid": float(p.total_commission_paid),
        "commission_pending": float(p.total_commission_earned - p.total_commission_paid),
        "notes": p.notes,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }

def _deal_dict(d: PartnerDeal) -> dict:
    return {
        "id": str(d.id), "partner_id": str(d.partner_id),
        "customer_id": str(d.customer_id) if d.customer_id else None,
        "invoice_id": str(d.invoice_id) if d.invoice_id else None,
        "deal_name": d.deal_name, "stage": d.stage,
        "deal_value": float(d.deal_value), "commission_amount": float(d.commission_amount),
        "approved_at": d.approved_at.isoformat() if d.approved_at else None,
        "paid_at": d.paid_at.isoformat() if d.paid_at else None,
        "notes": d.notes,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }
