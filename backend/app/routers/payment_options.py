"""Payment options router — staff-side endpoints.

GET  /api/payment-options/plans              — list payment plans for org
POST /api/payment-options/plans              — create a payment plan
GET  /api/payment-options/plans/{id}         — plan detail + instalments
PATCH /api/payment-options/plans/{id}/instalments/{inst_id} — mark instalment paid

GET  /api/payment-options/discounts          — list early-payment discounts
POST /api/payment-options/discounts          — create early-payment discount
DELETE /api/payment-options/discounts/{id}   — remove discount

GET  /api/payment-options/deposits           — list deposit requests
POST /api/payment-options/deposits           — create deposit request
PATCH /api/payment-options/deposits/{id}     — mark deposit paid

GET  /api/payment-options/ndas               — list NDA agreements for org
POST /api/payment-options/ndas               — create NDA for a customer

GET  /api/payment-options/terms              — list portal terms acceptances
"""
import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.payment_options import (
    DepositRequest,
    EarlyPaymentDiscount,
    NdaAgreement,
    PaymentPlan,
    PaymentPlanInstalment,
    PortalTermsAcceptance,
)

logger = logging.getLogger(__name__)
from app.middleware.plan_check import require_module
router = APIRouter(prefix="/api/payment-options", tags=["payment-options"], dependencies=[Depends(require_module("invoicing"))])


# ── Schemas ───────────────────────────────────────────────────────────────────

class InstalmentIn(BaseModel):
    instalment_number: int
    amount: float
    due_date: str  # ISO date


class PaymentPlanCreate(BaseModel):
    invoice_id: str
    customer_id: str
    total_amount: float
    currency: str = "SEK"
    num_instalments: int
    instalments: list[InstalmentIn] = []


class DiscountCreate(BaseModel):
    invoice_id: str
    discount_pct: float
    days_threshold: int
    discounted_total: float


class DepositCreate(BaseModel):
    customer_id: str
    amount: float
    currency: str = "SEK"
    invoice_id: str | None = None
    quote_id: str | None = None


class DepositPatch(BaseModel):
    status: str
    payment_method: str | None = None


class NdaCreate(BaseModel):
    customer_id: str
    title: str
    body: str


# ── Payment Plans ─────────────────────────────────────────────────────────────

@router.get("/plans")
async def list_plans(
    invoice_id: str | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = (
            select(PaymentPlan)
            .where(PaymentPlan.org_id == org_id)
            .options(selectinload(PaymentPlan.instalments))
            .order_by(PaymentPlan.created_at.desc())
        )
        if invoice_id:
            q = q.where(PaymentPlan.invoice_id == uuid.UUID(invoice_id))
        rows = (await db.execute(q)).scalars().all()
        return [
            {
                "id": str(r.id),
                "invoice_id": str(r.invoice_id),
                "customer_id": str(r.customer_id),
                "total_amount": float(r.total_amount),
                "currency": r.currency,
                "num_instalments": r.num_instalments,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
                "instalments": [
                    {
                        "id": str(i.id),
                        "instalment_number": i.instalment_number,
                        "amount": float(i.amount),
                        "due_date": str(i.due_date),
                        "status": i.status,
                        "paid_at": i.paid_at.isoformat() if i.paid_at else None,
                    }
                    for i in sorted(r.instalments, key=lambda x: x.instalment_number)
                ],
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_plans failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/plans", status_code=201)
async def create_plan(
    body: PaymentPlanCreate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        plan = PaymentPlan(
            org_id=org_id,
            invoice_id=uuid.UUID(body.invoice_id),
            customer_id=uuid.UUID(body.customer_id),
            total_amount=Decimal(str(body.total_amount)),
            currency=body.currency,
            num_instalments=body.num_instalments,
        )
        db.add(plan)
        await db.flush()
        for inst in body.instalments:
            db.add(PaymentPlanInstalment(
                plan_id=plan.id,
                instalment_number=inst.instalment_number,
                amount=Decimal(str(inst.amount)),
                due_date=date.fromisoformat(inst.due_date),
            ))
        await db.commit()
        return {"id": str(plan.id)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_plan failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/plans/{plan_id}/instalments/{inst_id}")
async def mark_instalment_paid(
    plan_id: str,
    inst_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        plan = await db.scalar(
            select(PaymentPlan).where(
                PaymentPlan.id == uuid.UUID(plan_id),
                PaymentPlan.org_id == org_id,
            )
        )
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        inst = await db.scalar(
            select(PaymentPlanInstalment).where(
                PaymentPlanInstalment.id == uuid.UUID(inst_id),
                PaymentPlanInstalment.plan_id == plan.id,
            )
        )
        if not inst:
            raise HTTPException(status_code=404, detail="Instalment not found")
        inst.status = "paid"
        inst.paid_at = datetime.now(timezone.utc)
        await db.commit()
        return {"status": "paid"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("mark_instalment_paid failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Early Payment Discounts ───────────────────────────────────────────────────

@router.get("/discounts")
async def list_discounts(
    invoice_id: str | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = (
            select(EarlyPaymentDiscount)
            .where(EarlyPaymentDiscount.org_id == org_id)
            .order_by(EarlyPaymentDiscount.created_at.desc())
        )
        if invoice_id:
            q = q.where(EarlyPaymentDiscount.invoice_id == uuid.UUID(invoice_id))
        rows = (await db.execute(q)).scalars().all()
        return [
            {
                "id": str(r.id),
                "invoice_id": str(r.invoice_id),
                "discount_pct": float(r.discount_pct),
                "days_threshold": r.days_threshold,
                "discounted_total": float(r.discounted_total),
                "accepted_at": r.accepted_at.isoformat() if r.accepted_at else None,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_discounts failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/discounts", status_code=201)
async def create_discount(
    body: DiscountCreate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        disc = EarlyPaymentDiscount(
            org_id=org_id,
            invoice_id=uuid.UUID(body.invoice_id),
            discount_pct=Decimal(str(body.discount_pct)),
            days_threshold=body.days_threshold,
            discounted_total=Decimal(str(body.discounted_total)),
        )
        db.add(disc)
        await db.commit()
        return {"id": str(disc.id)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_discount failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/discounts/{discount_id}", status_code=204)
async def delete_discount(
    discount_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        disc = await db.scalar(
            select(EarlyPaymentDiscount).where(
                EarlyPaymentDiscount.id == uuid.UUID(discount_id),
                EarlyPaymentDiscount.org_id == org_id,
            )
        )
        if not disc:
            raise HTTPException(status_code=404, detail="Discount not found")
        await db.delete(disc)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_discount failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Deposit Requests ──────────────────────────────────────────────────────────

@router.get("/deposits")
async def list_deposits(
    customer_id: str | None = None,
    status: str | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = (
            select(DepositRequest)
            .where(DepositRequest.org_id == org_id)
            .order_by(DepositRequest.created_at.desc())
        )
        if customer_id:
            q = q.where(DepositRequest.customer_id == uuid.UUID(customer_id))
        if status:
            q = q.where(DepositRequest.status == status)
        rows = (await db.execute(q)).scalars().all()
        return [
            {
                "id": str(r.id),
                "customer_id": str(r.customer_id),
                "invoice_id": str(r.invoice_id) if r.invoice_id else None,
                "quote_id": str(r.quote_id) if r.quote_id else None,
                "amount": float(r.amount),
                "currency": r.currency,
                "status": r.status,
                "payment_method": r.payment_method,
                "paid_at": r.paid_at.isoformat() if r.paid_at else None,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_deposits failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/deposits", status_code=201)
async def create_deposit(
    body: DepositCreate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        dep = DepositRequest(
            org_id=org_id,
            customer_id=uuid.UUID(body.customer_id),
            amount=Decimal(str(body.amount)),
            currency=body.currency,
            invoice_id=uuid.UUID(body.invoice_id) if body.invoice_id else None,
            quote_id=uuid.UUID(body.quote_id) if body.quote_id else None,
        )
        db.add(dep)
        await db.commit()
        return {"id": str(dep.id)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_deposit failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/deposits/{deposit_id}")
async def update_deposit(
    deposit_id: str,
    body: DepositPatch,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        dep = await db.scalar(
            select(DepositRequest).where(
                DepositRequest.id == uuid.UUID(deposit_id),
                DepositRequest.org_id == org_id,
            )
        )
        if not dep:
            raise HTTPException(status_code=404, detail="Deposit not found")
        dep.status = body.status
        if body.payment_method:
            dep.payment_method = body.payment_method
        if body.status == "paid" and not dep.paid_at:
            dep.paid_at = datetime.now(timezone.utc)
        await db.commit()
        return {"status": dep.status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_deposit failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── NDA Agreements ────────────────────────────────────────────────────────────

@router.get("/ndas")
async def list_ndas(
    customer_id: str | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = (
            select(NdaAgreement)
            .where(NdaAgreement.org_id == org_id)
            .order_by(NdaAgreement.created_at.desc())
        )
        if customer_id:
            q = q.where(NdaAgreement.customer_id == uuid.UUID(customer_id))
        rows = (await db.execute(q)).scalars().all()
        return [
            {
                "id": str(r.id),
                "customer_id": str(r.customer_id),
                "title": r.title,
                "status": r.status,
                "signed_at": r.signed_at.isoformat() if r.signed_at else None,
                "signer_name": r.signer_name,
                "signer_email": r.signer_email,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_ndas failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/ndas", status_code=201)
async def create_nda(
    body: NdaCreate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        nda = NdaAgreement(
            org_id=org_id,
            customer_id=uuid.UUID(body.customer_id),
            title=body.title,
            body=body.body,
        )
        db.add(nda)
        await db.commit()
        return {"id": str(nda.id)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_nda failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/ndas/{nda_id}")
async def get_nda(
    nda_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        nda = await db.scalar(
            select(NdaAgreement).where(
                NdaAgreement.id == uuid.UUID(nda_id),
                NdaAgreement.org_id == org_id,
            )
        )
        if not nda:
            raise HTTPException(status_code=404, detail="NDA not found")
        return {
            "id": str(nda.id),
            "customer_id": str(nda.customer_id),
            "title": nda.title,
            "body": nda.body,
            "status": nda.status,
            "signed_at": nda.signed_at.isoformat() if nda.signed_at else None,
            "signer_name": nda.signer_name,
            "signer_email": nda.signer_email,
            "signature_hash": nda.signature_hash,
            "created_at": nda.created_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_nda failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Portal Terms Acceptances ──────────────────────────────────────────────────

@router.get("/terms")
async def list_terms_acceptances(
    customer_id: str | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = (
            select(PortalTermsAcceptance)
            .where(PortalTermsAcceptance.org_id == org_id)
            .order_by(PortalTermsAcceptance.accepted_at.desc())
        )
        if customer_id:
            q = q.where(PortalTermsAcceptance.customer_id == uuid.UUID(customer_id))
        rows = (await db.execute(q)).scalars().all()
        return [
            {
                "id": str(r.id),
                "customer_id": str(r.customer_id),
                "terms_version": r.terms_version,
                "accepted_at": r.accepted_at.isoformat(),
                "ip_address": r.ip_address,
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_terms_acceptances failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")
