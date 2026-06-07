"""Insurance — manage policies and claims.

Endpoints
─────────
GET    /api/insurance/policies                          → list policies
POST   /api/insurance/policies                          → create policy
GET    /api/insurance/policies/{id}                     → detail
PATCH  /api/insurance/policies/{id}                     → update
DELETE /api/insurance/policies/{id}                     → delete
GET    /api/insurance/policies/{policy_id}/claims       → list claims
POST   /api/insurance/policies/{policy_id}/claims       → add claim
PATCH  /api/insurance/claims/{id}                       → update claim
GET    /api/insurance/renewals                          → upcoming renewals
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.insurance import InsuranceClaim, InsurancePolicy
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/insurance", tags=["insurance"], dependencies=[Depends(require_module("finance"))])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _policy_out(p: InsurancePolicy) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "org_id": str(p.org_id),
        "policy_name": p.policy_name,
        "insurer": p.insurer,
        "policy_number": p.policy_number,
        "type": p.type,
        "coverage_amount": float(p.coverage_amount) if p.coverage_amount is not None else None,
        "currency": p.currency,
        "premium_annual": float(p.premium_annual) if p.premium_annual is not None else None,
        "start_date": p.start_date.isoformat() if p.start_date else None,
        "end_date": p.end_date.isoformat() if p.end_date else None,
        "renewal_due": p.renewal_due.isoformat() if p.renewal_due else None,
        "renewal_reminder_days": p.renewal_reminder_days,
        "status": p.status,
        "notes": p.notes,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }


def _claim_out(c: InsuranceClaim) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "policy_id": str(c.policy_id),
        "org_id": str(c.org_id),
        "claim_date": c.claim_date.isoformat() if c.claim_date else None,
        "description": c.description,
        "amount_claimed": float(c.amount_claimed) if c.amount_claimed is not None else None,
        "amount_settled": float(c.amount_settled) if c.amount_settled is not None else None,
        "status": c.status,
        "settled_at": c.settled_at.isoformat() if c.settled_at else None,
        "created_at": c.created_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class PolicyIn(BaseModel):
    policy_name: str = Field(min_length=1, max_length=300)
    insurer: Optional[str] = Field(default=None, max_length=200)
    policy_number: Optional[str] = Field(default=None, max_length=100)
    type: str = Field(default="other")
    coverage_amount: Optional[float] = None
    currency: str = Field(default="SEK", max_length=3)
    premium_annual: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    renewal_due: Optional[date] = None
    renewal_reminder_days: int = Field(default=30)
    status: str = Field(default="active")
    notes: Optional[str] = None


class PolicyPatch(BaseModel):
    policy_name: Optional[str] = Field(default=None, max_length=300)
    insurer: Optional[str] = Field(default=None, max_length=200)
    policy_number: Optional[str] = Field(default=None, max_length=100)
    type: Optional[str] = None
    coverage_amount: Optional[float] = None
    currency: Optional[str] = Field(default=None, max_length=3)
    premium_annual: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    renewal_due: Optional[date] = None
    renewal_reminder_days: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class ClaimIn(BaseModel):
    claim_date: Optional[date] = None
    description: Optional[str] = None
    amount_claimed: Optional[float] = None
    status: str = Field(default="open")


class ClaimPatch(BaseModel):
    claim_date: Optional[date] = None
    description: Optional[str] = None
    amount_claimed: Optional[float] = None
    amount_settled: Optional[float] = None
    status: Optional[str] = None
    settled_at: Optional[datetime] = None


# ── Policy Endpoints ───────────────────────────────────────────────────────────

@router.get("/policies")
async def list_policies(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        rows = (await db.execute(
            select(InsurancePolicy).where(InsurancePolicy.org_id == org_id)
            .order_by(InsurancePolicy.created_at.desc())
        )).scalars().all()
        return [_policy_out(p) for p in rows]
    except Exception as e:
        log.error("list_policies failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/policies", status_code=201)
async def create_policy(
    body: PolicyIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        policy = InsurancePolicy(
            org_id=org_id,
            policy_name=body.policy_name,
            insurer=body.insurer,
            policy_number=body.policy_number,
            type=body.type,
            coverage_amount=body.coverage_amount,
            currency=body.currency,
            premium_annual=body.premium_annual,
            start_date=body.start_date,
            end_date=body.end_date,
            renewal_due=body.renewal_due,
            renewal_reminder_days=body.renewal_reminder_days,
            status=body.status,
            notes=body.notes,
        )
        db.add(policy)
        await db.commit()
        await db.refresh(policy)
        return _policy_out(policy)
    except Exception as e:
        log.error("create_policy failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/policies/{policy_id}")
async def get_policy(
    policy_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        policy = await db.scalar(
            select(InsurancePolicy).where(
                InsurancePolicy.id == policy_id, InsurancePolicy.org_id == org_id
            )
        )
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")
        return _policy_out(policy)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_policy failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/policies/{policy_id}")
async def patch_policy(
    policy_id: uuid.UUID,
    body: PolicyPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        policy = await db.scalar(
            select(InsurancePolicy).where(
                InsurancePolicy.id == policy_id, InsurancePolicy.org_id == org_id
            )
        )
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")

        for field in (
            "policy_name", "insurer", "policy_number", "type", "coverage_amount",
            "currency", "premium_annual", "start_date", "end_date", "renewal_due",
            "renewal_reminder_days", "status", "notes",
        ):
            val = getattr(body, field)
            if val is not None:
                setattr(policy, field, val)

        policy.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(policy)
        return _policy_out(policy)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_policy failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/policies/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        policy = await db.scalar(
            select(InsurancePolicy).where(
                InsurancePolicy.id == policy_id, InsurancePolicy.org_id == org_id
            )
        )
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")
        await db.delete(policy)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_policy failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Claim Endpoints ────────────────────────────────────────────────────────────

@router.get("/policies/{policy_id}/claims")
async def list_claims(
    policy_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        policy = await db.scalar(
            select(InsurancePolicy).where(
                InsurancePolicy.id == policy_id, InsurancePolicy.org_id == org_id
            )
        )
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")

        rows = (await db.execute(
            select(InsuranceClaim).where(InsuranceClaim.policy_id == policy_id)
            .order_by(InsuranceClaim.created_at.desc())
        )).scalars().all()
        return [_claim_out(c) for c in rows]
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_claims failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/policies/{policy_id}/claims", status_code=201)
async def create_claim(
    policy_id: uuid.UUID,
    body: ClaimIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        policy = await db.scalar(
            select(InsurancePolicy).where(
                InsurancePolicy.id == policy_id, InsurancePolicy.org_id == org_id
            )
        )
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")

        claim = InsuranceClaim(
            policy_id=policy_id,
            org_id=org_id,
            claim_date=body.claim_date,
            description=body.description,
            amount_claimed=body.amount_claimed,
            status=body.status,
        )
        db.add(claim)
        await db.commit()
        await db.refresh(claim)
        return _claim_out(claim)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_claim failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/claims/{claim_id}")
async def patch_claim(
    claim_id: uuid.UUID,
    body: ClaimPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        claim = await db.scalar(
            select(InsuranceClaim).where(
                InsuranceClaim.id == claim_id, InsuranceClaim.org_id == org_id
            )
        )
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")

        for field in ("claim_date", "description", "amount_claimed", "amount_settled", "status", "settled_at"):
            val = getattr(body, field)
            if val is not None:
                setattr(claim, field, val)

        await db.commit()
        await db.refresh(claim)
        return _claim_out(claim)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_claim failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Renewals Endpoint ──────────────────────────────────────────────────────────

@router.get("/renewals")
async def upcoming_renewals(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Policies where renewal_due <= today + renewal_reminder_days, sorted by renewal_due asc."""
    org_id = _org_id(ctx)
    try:
        today = date.today()
        rows = (await db.execute(
            select(InsurancePolicy).where(InsurancePolicy.org_id == org_id)
            .order_by(InsurancePolicy.renewal_due.asc())
        )).scalars().all()

        result = []
        for p in rows:
            if p.renewal_due is None:
                continue
            cutoff = today + timedelta(days=p.renewal_reminder_days or 30)
            if p.renewal_due <= cutoff:
                result.append(_policy_out(p))
        return result
    except Exception as e:
        log.error("upcoming_renewals failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
