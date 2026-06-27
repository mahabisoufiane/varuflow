"""Franchise management

Handles franchisee onboarding, royalty billing, and central product catalogue push.

Endpoints:
  GET  /api/franchise/agreements
  POST /api/franchise/agreements
  GET  /api/franchise/agreements/{id}
  PATCH /api/franchise/agreements/{id}

  GET  /api/franchise/royalties
  POST /api/franchise/royalties/calculate/{agreement_id}/{period}
  POST /api/franchise/royalties/{id}/send
  PATCH /api/franchise/royalties/{id}/mark-paid

  POST /api/franchise/catalog/push
  GET  /api/franchise/catalog/pushes
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.features.inventory.models import Product
from app.features.corporate.model_multi_entity import FranchiseAgreement, FranchiseCatalogPush, RoyaltyBilling
from app.features.auth.organization import Organization
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/franchise", tags=["franchise"], dependencies=[Depends(require_module("analytics"))])
log = logging.getLogger(__name__)


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Schemas ───────────────────────────────────────────────────────────────────

class AgreementIn(BaseModel):
    franchisee_name: str
    franchisee_email: str
    franchisee_country: Optional[str] = None
    royalty_rate: float = 0.05          # 0.05 = 5%
    royalty_basis: str = "gross_revenue"  # gross_revenue|net_revenue|fixed
    fixed_royalty_amount: Optional[float] = None
    currency: str = "SEK"
    billing_cycle: str = "monthly"
    start_date: Optional[date] = None
    notes: Optional[str] = None

class AgreementPatch(BaseModel):
    royalty_rate: Optional[float] = None
    royalty_basis: Optional[str] = None
    fixed_royalty_amount: Optional[float] = None
    billing_cycle: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None

class AgreementOut(BaseModel):
    id: str
    franchisee_name: str
    franchisee_email: str
    franchisee_country: Optional[str]
    royalty_rate: str
    royalty_basis: str
    fixed_royalty_amount: Optional[str]
    currency: str
    billing_cycle: str
    status: str
    start_date: Optional[str]
    end_date: Optional[str]
    franchisee_org_id: Optional[str]

class RoyaltyOut(BaseModel):
    id: str
    agreement_id: str
    period: str
    revenue_basis: Optional[str]
    royalty_amount: str
    currency: str
    status: str
    due_date: Optional[str]
    paid_at: Optional[str]
    invoice_id: Optional[str]

class CatalogPushIn(BaseModel):
    franchisee_org_id: uuid.UUID
    product_ids: Optional[list[uuid.UUID]] = None  # None = push ALL

class CatalogPushOut(BaseModel):
    id: str
    franchisee_org_id: str
    pushed_count: int
    created_count: int
    updated_count: int
    status: str
    created_at: str


def _a_out(a: FranchiseAgreement) -> AgreementOut:
    return AgreementOut(
        id=str(a.id), franchisee_name=a.franchisee_name, franchisee_email=a.franchisee_email,
        franchisee_country=a.franchisee_country, royalty_rate=str(a.royalty_rate),
        royalty_basis=a.royalty_basis,
        fixed_royalty_amount=str(a.fixed_royalty_amount) if a.fixed_royalty_amount else None,
        currency=a.currency, billing_cycle=a.billing_cycle, status=a.status,
        start_date=a.start_date.isoformat() if a.start_date else None,
        end_date=a.end_date.isoformat() if a.end_date else None,
        franchisee_org_id=str(a.franchisee_org_id) if a.franchisee_org_id else None,
    )


def _r_out(r: RoyaltyBilling) -> RoyaltyOut:
    return RoyaltyOut(
        id=str(r.id), agreement_id=str(r.agreement_id), period=r.period,
        revenue_basis=str(r.revenue_basis) if r.revenue_basis else None,
        royalty_amount=str(r.royalty_amount), currency=r.currency, status=r.status,
        due_date=r.due_date.isoformat() if r.due_date else None,
        paid_at=r.paid_at.isoformat() if r.paid_at else None,
        invoice_id=str(r.invoice_id) if r.invoice_id else None,
    )


def _p_out(p: FranchiseCatalogPush) -> CatalogPushOut:
    return CatalogPushOut(
        id=str(p.id), franchisee_org_id=str(p.franchisee_org_id),
        pushed_count=p.pushed_count, created_count=p.created_count, updated_count=p.updated_count,
        status=p.status, created_at=p.created_at.isoformat(),
    )


# ── Endpoints — Agreements ─────────────────────────────────────────────────────

@router.get("/agreements")
async def list_agreements(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        q = select(FranchiseAgreement).where(FranchiseAgreement.franchisor_org_id == org_id)
        if status:
            q = q.where(FranchiseAgreement.status == status)
        count_row = await db.execute(
            select(func.count(FranchiseAgreement.id)).where(FranchiseAgreement.franchisor_org_id == org_id)
        )
        total = count_row.scalar_one() or 0
        rows = await db.execute(q.order_by(FranchiseAgreement.created_at.desc()).limit(limit).offset((page - 1) * limit))
        return {"agreements": [_a_out(a) for a in rows.scalars()], "total": total}
    except Exception as e:
        log.error("list_agreements failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/agreements", response_model=AgreementOut)
async def create_agreement(
    body: AgreementIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        agreement = FranchiseAgreement(
            franchisor_org_id=org_id,
            franchisee_name=body.franchisee_name,
            franchisee_email=body.franchisee_email,
            franchisee_country=body.franchisee_country,
            royalty_rate=Decimal(str(body.royalty_rate)),
            royalty_basis=body.royalty_basis,
            fixed_royalty_amount=Decimal(str(body.fixed_royalty_amount)) if body.fixed_royalty_amount else None,
            currency=body.currency,
            billing_cycle=body.billing_cycle,
            start_date=body.start_date,
            notes=body.notes,
        )
        db.add(agreement)
        await db.commit()
        await db.refresh(agreement)
        return _a_out(agreement)
    except Exception as e:
        log.error("create_agreement failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/agreements/{agreement_id}", response_model=AgreementOut)
async def get_agreement(
    agreement_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(FranchiseAgreement).where(
                FranchiseAgreement.id == agreement_id,
                FranchiseAgreement.franchisor_org_id == org_id,
            )
        )
        a = row.scalar_one_or_none()
        if not a:
            raise HTTPException(status_code=404, detail="Agreement not found")
        return _a_out(a)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_agreement failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/agreements/{agreement_id}", response_model=AgreementOut)
async def update_agreement(
    agreement_id: uuid.UUID,
    body: AgreementPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(FranchiseAgreement).where(
                FranchiseAgreement.id == agreement_id,
                FranchiseAgreement.franchisor_org_id == org_id,
            )
        )
        a = row.scalar_one_or_none()
        if not a:
            raise HTTPException(status_code=404, detail="Agreement not found")
        if body.royalty_rate is not None:
            a.royalty_rate = Decimal(str(body.royalty_rate))
        if body.royalty_basis is not None:
            a.royalty_basis = body.royalty_basis
        if body.fixed_royalty_amount is not None:
            a.fixed_royalty_amount = Decimal(str(body.fixed_royalty_amount))
        if body.billing_cycle is not None:
            a.billing_cycle = body.billing_cycle
        if body.status is not None:
            a.status = body.status
        if body.start_date is not None:
            a.start_date = body.start_date
        if body.end_date is not None:
            a.end_date = body.end_date
        if body.notes is not None:
            a.notes = body.notes
        await db.commit()
        return _a_out(a)
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_agreement failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Endpoints — Royalty Billing ────────────────────────────────────────────────

@router.get("/royalties")
async def list_royalties(
    agreement_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        q = select(RoyaltyBilling).where(RoyaltyBilling.franchisor_org_id == org_id)
        if agreement_id:
            q = q.where(RoyaltyBilling.agreement_id == agreement_id)
        if status:
            q = q.where(RoyaltyBilling.status == status)
        count_row = await db.execute(
            select(func.count(RoyaltyBilling.id)).where(RoyaltyBilling.franchisor_org_id == org_id)
        )
        total = count_row.scalar_one() or 0
        rows = await db.execute(q.order_by(RoyaltyBilling.period.desc()).limit(limit).offset((page - 1) * limit))
        return {"royalties": [_r_out(r) for r in rows.scalars()], "total": total}
    except Exception as e:
        log.error("list_royalties failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


class RoyaltyCalculateIn(BaseModel):
    revenue_basis: Optional[float] = None   # required unless agreement is fixed


@router.post("/royalties/calculate/{agreement_id}/{period}", response_model=RoyaltyOut)
async def calculate_royalty(
    agreement_id: uuid.UUID,
    period: str,    # YYYY-MM
    body: RoyaltyCalculateIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Calculate and draft a royalty billing for a period. Idempotent — updates if draft exists."""
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(FranchiseAgreement).where(
                FranchiseAgreement.id == agreement_id,
                FranchiseAgreement.franchisor_org_id == org_id,
            )
        )
        agreement = row.scalar_one_or_none()
        if not agreement:
            raise HTTPException(status_code=404, detail="Agreement not found")

        # Calculate royalty amount
        if agreement.royalty_basis == "fixed":
            royalty_amount = agreement.fixed_royalty_amount or Decimal("0")
        else:
            if body.revenue_basis is None:
                raise HTTPException(status_code=422, detail="revenue_basis required for non-fixed agreements")
            royalty_amount = Decimal(str(body.revenue_basis)) * agreement.royalty_rate

        # Idempotent: update existing draft if present
        existing_row = await db.execute(
            select(RoyaltyBilling).where(
                RoyaltyBilling.agreement_id == agreement_id,
                RoyaltyBilling.period == period,
                RoyaltyBilling.status == "draft",
            )
        )
        existing = existing_row.scalar_one_or_none()

        if existing:
            existing.revenue_basis = Decimal(str(body.revenue_basis)) if body.revenue_basis else None
            existing.royalty_amount = royalty_amount
            await db.commit()
            await db.refresh(existing)
            return _r_out(existing)

        billing = RoyaltyBilling(
            agreement_id=agreement_id,
            franchisor_org_id=org_id,
            franchisee_org_id=agreement.franchisee_org_id,
            period=period,
            revenue_basis=Decimal(str(body.revenue_basis)) if body.revenue_basis else None,
            royalty_amount=royalty_amount,
            currency=agreement.currency,
        )
        db.add(billing)
        await db.commit()
        await db.refresh(billing)
        return _r_out(billing)
    except HTTPException:
        raise
    except Exception as e:
        log.error("calculate_royalty failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/royalties/{royalty_id}/send", response_model=RoyaltyOut)
async def send_royalty(
    royalty_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Mark a royalty billing as 'sent' (invoice issued to franchisee)."""
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(RoyaltyBilling).where(
                RoyaltyBilling.id == royalty_id,
                RoyaltyBilling.franchisor_org_id == org_id,
            )
        )
        billing = row.scalar_one_or_none()
        if not billing:
            raise HTTPException(status_code=404, detail="Royalty billing not found")
        if billing.status != "draft":
            raise HTTPException(status_code=422, detail="Only draft billings can be sent")
        billing.status = "sent"
        await db.commit()
        await db.refresh(billing)
        return _r_out(billing)
    except HTTPException:
        raise
    except Exception as e:
        log.error("send_royalty failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/royalties/{royalty_id}/mark-paid", response_model=RoyaltyOut)
async def mark_paid(
    royalty_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(RoyaltyBilling).where(
                RoyaltyBilling.id == royalty_id,
                RoyaltyBilling.franchisor_org_id == org_id,
            )
        )
        billing = row.scalar_one_or_none()
        if not billing:
            raise HTTPException(status_code=404, detail="Royalty billing not found")
        billing.status = "paid"
        billing.paid_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(billing)
        return _r_out(billing)
    except HTTPException:
        raise
    except Exception as e:
        log.error("mark_royalty_paid failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Endpoints — Catalogue Push ─────────────────────────────────────────────────

@router.post("/catalog/push", response_model=CatalogPushOut)
async def push_catalog(
    body: CatalogPushIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Copy / upsert products from this org to a franchisee org."""
    org_id = _org(ctx)
    try:
        # Verify franchisee is in the same network
        fa_row = await db.execute(
            select(FranchiseAgreement).where(
                FranchiseAgreement.franchisor_org_id == org_id,
                FranchiseAgreement.franchisee_org_id == body.franchisee_org_id,
                FranchiseAgreement.status == "active",
            )
        )
        if not fa_row.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="No active franchise agreement with this franchisee")

        # Fetch products to push
        prod_q = select(Product).where(Product.org_id == org_id)
        if body.product_ids:
            prod_q = prod_q.where(Product.id.in_(body.product_ids))
        prod_rows = await db.execute(prod_q)
        products = prod_rows.scalars().all()

        created_count = 0
        updated_count = 0

        for src in products:
            # Check if franchisee already has a product with matching SKU
            existing_row = await db.execute(
                select(Product).where(
                    Product.org_id == body.franchisee_org_id,
                    Product.sku == src.sku,
                )
            )
            existing = existing_row.scalar_one_or_none()
            if existing:
                existing.name = src.name
                existing.description = src.description
                existing.price = src.price
                existing.cost = src.cost
                existing.unit = src.unit
                updated_count += 1
            else:
                clone = Product(
                    org_id=body.franchisee_org_id,
                    name=src.name,
                    sku=src.sku,
                    description=src.description,
                    price=src.price,
                    cost=src.cost,
                    unit=src.unit,
                    stock_quantity=Decimal("0"),
                )
                db.add(clone)
                created_count += 1

        await db.flush()

        push_log = FranchiseCatalogPush(
            franchisor_org_id=org_id,
            franchisee_org_id=body.franchisee_org_id,
            product_ids=[str(p.id) for p in products],
            pushed_count=len(products),
            created_count=created_count,
            updated_count=updated_count,
            status="completed",
        )
        db.add(push_log)
        await db.commit()
        await db.refresh(push_log)
        return _p_out(push_log)
    except HTTPException:
        raise
    except Exception as e:
        log.error("push_catalog failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/catalog/pushes")
async def list_catalog_pushes(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        count_row = await db.execute(
            select(func.count(FranchiseCatalogPush.id)).where(FranchiseCatalogPush.franchisor_org_id == org_id)
        )
        total = count_row.scalar_one() or 0
        rows = await db.execute(
            select(FranchiseCatalogPush)
            .where(FranchiseCatalogPush.franchisor_org_id == org_id)
            .order_by(FranchiseCatalogPush.created_at.desc())
            .limit(limit).offset((page - 1) * limit)
        )
        return {"pushes": [_p_out(p) for p in rows.scalars()], "total": total}
    except Exception as e:
        log.error("list_catalog_pushes failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
