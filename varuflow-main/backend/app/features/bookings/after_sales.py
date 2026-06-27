"""After-sales router — staff-side endpoints.

Return/refund requests, warranty records, satisfaction surveys, upsell suggestions.

GET  /api/after-sales/returns                — list return requests
POST /api/after-sales/returns                — (staff) create on behalf of customer
PATCH /api/after-sales/returns/{id}          — update status / add resolution

GET  /api/after-sales/warranties             — list warranty records
POST /api/after-sales/warranties             — register warranty
PATCH /api/after-sales/warranties/{id}       — update status / notes

GET  /api/after-sales/surveys                — list satisfaction surveys
POST /api/after-sales/surveys                — create survey (generates magic-link token)
GET  /api/after-sales/surveys/{id}           — detail

GET  /api/after-sales/upsells                — list upsell suggestions
POST /api/after-sales/upsells                — create suggestion for a customer
DELETE /api/after-sales/upsells/{id}         — remove suggestion
"""
import logging
import secrets
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.features.bookings.model_after_sales import (
    ReturnRequest,
    SatisfactionSurvey,
    UpsellSuggestion,
    WarrantyRecord,
)

logger = logging.getLogger(__name__)
from app.middleware.plan_check import require_module
router = APIRouter(prefix="/api/after-sales", tags=["after-sales"], dependencies=[Depends(require_module("analytics"))])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ReturnCreate(BaseModel):
    customer_id: str
    invoice_id: str | None = None
    product_id: str | None = None
    quantity: float | None = None
    reason: str = "other"
    description: str | None = None


class ReturnPatch(BaseModel):
    status: str | None = None
    resolution_notes: str | None = None
    refund_amount: float | None = None


class WarrantyCreate(BaseModel):
    customer_id: str
    invoice_id: str | None = None
    product_id: str | None = None
    serial_number: str | None = None
    product_name_snapshot: str | None = None
    warranty_months: int = 12
    starts_at: str  # ISO date
    notes: str | None = None


class WarrantyPatch(BaseModel):
    status: str | None = None
    notes: str | None = None


class SurveyCreate(BaseModel):
    customer_id: str
    reference_type: str  # invoice / project / appointment
    reference_id: str


class UpsellCreate(BaseModel):
    customer_id: str
    trigger_type: str  # post_invoice / post_project / post_appointment
    trigger_id: str
    product_ids: str | None = None  # comma-separated UUIDs or names
    message: str | None = None


# ── Return Requests ───────────────────────────────────────────────────────────

def _return_out(r: ReturnRequest) -> dict:
    return {
        "id": str(r.id),
        "customer_id": str(r.customer_id),
        "invoice_id": str(r.invoice_id) if r.invoice_id else None,
        "product_id": str(r.product_id) if r.product_id else None,
        "quantity": float(r.quantity) if r.quantity else None,
        "reason": r.reason,
        "description": r.description,
        "photo_url": r.photo_url,
        "status": r.status,
        "resolution_notes": r.resolution_notes,
        "refund_amount": float(r.refund_amount) if r.refund_amount else None,
        "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
        "created_at": r.created_at.isoformat(),
    }


@router.get("/returns")
async def list_returns(
    status: str | None = None,
    customer_id: str | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(ReturnRequest).where(ReturnRequest.org_id == org_id).order_by(ReturnRequest.created_at.desc())
        if status:
            q = q.where(ReturnRequest.status == status)
        if customer_id:
            q = q.where(ReturnRequest.customer_id == uuid.UUID(customer_id))
        rows = (await db.execute(q)).scalars().all()
        return [_return_out(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_returns failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/returns", status_code=201)
async def create_return(
    body: ReturnCreate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        rr = ReturnRequest(
            org_id=org_id,
            customer_id=uuid.UUID(body.customer_id),
            invoice_id=uuid.UUID(body.invoice_id) if body.invoice_id else None,
            product_id=uuid.UUID(body.product_id) if body.product_id else None,
            quantity=Decimal(str(body.quantity)) if body.quantity else None,
            reason=body.reason,
            description=body.description,
        )
        db.add(rr)
        await db.commit()
        return {"id": str(rr.id)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_return failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/returns/{return_id}")
async def update_return(
    return_id: str,
    body: ReturnPatch,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        rr = await db.scalar(
            select(ReturnRequest).where(ReturnRequest.id == uuid.UUID(return_id), ReturnRequest.org_id == org_id)
        )
        if not rr:
            raise HTTPException(status_code=404, detail="Return request not found")
        if body.status:
            rr.status = body.status
            if body.status in ("approved", "rejected", "refunded", "exchanged") and not rr.resolved_at:
                rr.resolved_at = datetime.now(timezone.utc)
        if body.resolution_notes is not None:
            rr.resolution_notes = body.resolution_notes
        if body.refund_amount is not None:
            rr.refund_amount = Decimal(str(body.refund_amount))
        await db.commit()
        return _return_out(rr)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_return failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


class ApproveReturn(BaseModel):
    refund_amount: float | None = None
    resolution_notes: str | None = None
    stripe_payment_intent_id: str | None = None  # if issuing Stripe refund


@router.post("/returns/{return_id}/approve")
async def approve_return(
    return_id: str,
    body: ApproveReturn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Approve a return: auto-creates draft credit note, restores stock, optionally issues Stripe refund."""
    try:
        import os
        org_id = member["org_id"]
        rr = await db.scalar(
            select(ReturnRequest).where(ReturnRequest.id == uuid.UUID(return_id), ReturnRequest.org_id == org_id)
        )
        if not rr:
            raise HTTPException(status_code=404, detail="Return request not found")
        if rr.status not in ("pending",):
            raise HTTPException(status_code=409, detail=f"Cannot approve a return in status '{rr.status}'")

        now = datetime.now(timezone.utc)
        rr.status = "approved"
        rr.resolved_at = now
        if body.resolution_notes:
            rr.resolution_notes = body.resolution_notes
        if body.refund_amount is not None:
            rr.refund_amount = Decimal(str(body.refund_amount))

        credit_note_id = None
        # Auto-create draft credit note
        try:
            from app.features.invoicing.credit_note import CreditNote
            cn = CreditNote(
                org_id=org_id,
                customer_id=rr.customer_id,
                invoice_id=rr.invoice_id,
                amount=rr.refund_amount or Decimal("0"),
                reason=f"Return #{str(rr.id)[:8]}" + (f": {rr.description[:80]}" if rr.description else ""),
                status="DRAFT",
                created_at=now,
            )
            db.add(cn)
            await db.flush()
            credit_note_id = str(cn.id)
        except Exception as cn_err:
            logger.warning("approve_return: could not create credit note: %s", cn_err)

        # Auto-restore stock if product is known
        if rr.product_id and rr.quantity:
            try:
                from app.features.inventory.models import StockMovement
                mv = StockMovement(
                    org_id=org_id,
                    product_id=rr.product_id,
                    movement_type="return",
                    quantity=rr.quantity,
                    notes=f"Return request {str(rr.id)[:8]} approved",
                    created_at=now,
                )
                db.add(mv)
            except Exception as stock_err:
                logger.warning("approve_return: could not adjust stock: %s", stock_err)

        await db.commit()

        # Stripe refund (fire and forget on failure)
        if body.stripe_payment_intent_id and rr.refund_amount:
            try:
                import stripe
                stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
                stripe.Refund.create(
                    payment_intent=body.stripe_payment_intent_id,
                    amount=int(rr.refund_amount * 100),
                )
            except Exception as stripe_err:
                logger.error("approve_return: Stripe refund failed: %s", stripe_err)

        return {**_return_out(rr), "credit_note_id": credit_note_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("approve_return failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")

def _warranty_out(w: WarrantyRecord) -> dict:
    return {
        "id": str(w.id),
        "customer_id": str(w.customer_id),
        "invoice_id": str(w.invoice_id) if w.invoice_id else None,
        "product_id": str(w.product_id) if w.product_id else None,
        "serial_number": w.serial_number,
        "product_name_snapshot": w.product_name_snapshot,
        "warranty_months": w.warranty_months,
        "starts_at": str(w.starts_at),
        "expires_at": str(w.expires_at),
        "status": w.status,
        "notes": w.notes,
        "created_at": w.created_at.isoformat(),
    }


@router.get("/warranties")
async def list_warranties(
    customer_id: str | None = None,
    status: str | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(WarrantyRecord).where(WarrantyRecord.org_id == org_id).order_by(WarrantyRecord.expires_at.asc())
        if customer_id:
            q = q.where(WarrantyRecord.customer_id == uuid.UUID(customer_id))
        if status:
            q = q.where(WarrantyRecord.status == status)
        rows = (await db.execute(q)).scalars().all()
        return [_warranty_out(w) for w in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_warranties failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/warranties", status_code=201)
async def create_warranty(
    body: WarrantyCreate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        from datetime import timedelta
        starts = date.fromisoformat(body.starts_at)
        # expires_at = starts + warranty_months months (approximate via days)
        expires = date(
            starts.year + (starts.month - 1 + body.warranty_months) // 12,
            (starts.month - 1 + body.warranty_months) % 12 + 1,
            starts.day,
        )
        w = WarrantyRecord(
            org_id=org_id,
            customer_id=uuid.UUID(body.customer_id),
            invoice_id=uuid.UUID(body.invoice_id) if body.invoice_id else None,
            product_id=uuid.UUID(body.product_id) if body.product_id else None,
            serial_number=body.serial_number,
            product_name_snapshot=body.product_name_snapshot,
            warranty_months=body.warranty_months,
            starts_at=starts,
            expires_at=expires,
            notes=body.notes,
        )
        db.add(w)
        await db.commit()
        return {"id": str(w.id)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_warranty failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/warranties/{warranty_id}")
async def update_warranty(
    warranty_id: str,
    body: WarrantyPatch,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        w = await db.scalar(
            select(WarrantyRecord).where(WarrantyRecord.id == uuid.UUID(warranty_id), WarrantyRecord.org_id == org_id)
        )
        if not w:
            raise HTTPException(status_code=404, detail="Warranty not found")
        if body.status:
            w.status = body.status
        if body.notes is not None:
            w.notes = body.notes
        await db.commit()
        return _warranty_out(w)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_warranty failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Satisfaction Surveys ──────────────────────────────────────────────────────

@router.get("/surveys")
async def list_surveys(
    customer_id: str | None = None,
    reference_type: str | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(SatisfactionSurvey).where(SatisfactionSurvey.org_id == org_id).order_by(SatisfactionSurvey.created_at.desc())
        if customer_id:
            q = q.where(SatisfactionSurvey.customer_id == uuid.UUID(customer_id))
        if reference_type:
            q = q.where(SatisfactionSurvey.reference_type == reference_type)
        rows = (await db.execute(q)).scalars().all()
        return [
            {
                "id": str(r.id),
                "customer_id": str(r.customer_id),
                "reference_type": r.reference_type,
                "reference_id": str(r.reference_id),
                "score": r.score,
                "comment": r.comment,
                "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_surveys failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/surveys", status_code=201)
async def create_survey(
    body: SurveyCreate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        token = secrets.token_urlsafe(32)[:64]
        s = SatisfactionSurvey(
            org_id=org_id,
            customer_id=uuid.UUID(body.customer_id),
            reference_type=body.reference_type,
            reference_id=uuid.UUID(body.reference_id),
            token=token,
        )
        db.add(s)
        await db.commit()
        return {"id": str(s.id), "token": token}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_survey failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


# Survey submit via magic token — no auth required (public)
from fastapi import APIRouter as _AR
public_router = _AR(prefix="/api/after-sales", tags=["after-sales-public"])


class SurveySubmit(BaseModel):
    score: int  # 1-5
    comment: str | None = None


@public_router.post("/surveys/submit/{token}")
async def submit_survey(
    token: str,
    body: SurveySubmit,
    db: AsyncSession = Depends(get_db),
):
    try:
        if not (1 <= body.score <= 5):
            raise HTTPException(status_code=422, detail="Score must be 1-5")
        s = await db.scalar(select(SatisfactionSurvey).where(SatisfactionSurvey.token == token))
        if not s:
            raise HTTPException(status_code=404, detail="Survey not found")
        if s.submitted_at:
            raise HTTPException(status_code=409, detail="Survey already submitted")
        s.score = body.score
        s.comment = body.comment
        s.submitted_at = datetime.now(timezone.utc)
        await db.commit()
        return {"submitted": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("submit_survey failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@public_router.get("/surveys/view/{token}")
async def view_survey(token: str, db: AsyncSession = Depends(get_db)):
    s = await db.scalar(select(SatisfactionSurvey).where(SatisfactionSurvey.token == token))
    if not s:
        raise HTTPException(status_code=404, detail="Survey not found")
    return {
        "reference_type": s.reference_type,
        "submitted": s.submitted_at is not None,
        "score": s.score,
    }


# ── Upsell Suggestions ────────────────────────────────────────────────────────

@router.get("/upsells")
async def list_upsells(
    customer_id: str | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(UpsellSuggestion).where(UpsellSuggestion.org_id == org_id).order_by(UpsellSuggestion.created_at.desc())
        if customer_id:
            q = q.where(UpsellSuggestion.customer_id == uuid.UUID(customer_id))
        rows = (await db.execute(q)).scalars().all()
        return [
            {
                "id": str(r.id),
                "customer_id": str(r.customer_id),
                "trigger_type": r.trigger_type,
                "trigger_id": str(r.trigger_id),
                "product_ids": r.product_ids,
                "message": r.message,
                "shown_at": r.shown_at.isoformat() if r.shown_at else None,
                "clicked_at": r.clicked_at.isoformat() if r.clicked_at else None,
                "dismissed_at": r.dismissed_at.isoformat() if r.dismissed_at else None,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_upsells failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/upsells", status_code=201)
async def create_upsell(
    body: UpsellCreate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        u = UpsellSuggestion(
            org_id=org_id,
            customer_id=uuid.UUID(body.customer_id),
            trigger_type=body.trigger_type,
            trigger_id=uuid.UUID(body.trigger_id),
            product_ids=body.product_ids,
            message=body.message,
        )
        db.add(u)
        await db.commit()
        return {"id": str(u.id)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_upsell failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/upsells/{upsell_id}", status_code=204)
async def delete_upsell(
    upsell_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        u = await db.scalar(
            select(UpsellSuggestion).where(UpsellSuggestion.id == uuid.UUID(upsell_id), UpsellSuggestion.org_id == org_id)
        )
        if not u:
            raise HTTPException(status_code=404, detail="Suggestion not found")
        await db.delete(u)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_upsell failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")
