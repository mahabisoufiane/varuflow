"""Purchase Requests router — staff request purchases, managers approve, PO generated."""
import logging
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from .models import PurchaseRequest, PurchaseRequestItem
from app.features.inventory.models import PurchaseOrder, PurchaseOrderItem
from app.features.auth.organization import OrgRole
from app.middleware.plan_check import require_module, require_role

logger = logging.getLogger(__name__)
router = APIRouter(tags=["purchase-requests"], dependencies=[Depends(require_module("inventory"))])

# Submitting a purchase request is open to any member; approving/rejecting one
# is a manager action (ADMIN+).
_MANAGER_ONLY = [Depends(require_role(OrgRole.ADMIN))]


class ItemIn(BaseModel):
    description: str
    quantity: int = 1
    unit_price: float
    product_id: str | None = None

class RequestCreate(BaseModel):
    title: str
    justification: str | None = None
    supplier_id: str | None = None
    estimated_total: float
    currency: str = "SEK"
    urgency: str = "normal"
    budget_category: str | None = None
    is_template: bool = False
    template_name: str | None = None
    items: list[ItemIn] = []

class ReviewBody(BaseModel):
    note: str | None = None


@router.get("/api/purchase-requests")
async def list_purchase_requests(
    status: str | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(PurchaseRequest).where(PurchaseRequest.org_id == org_id)
        if status:
            q = q.where(PurchaseRequest.status == status)
        # MEMBER sees only own requests
        role = member.get("role", "MEMBER")
        if role not in ("OWNER", "ADMIN"):
            q = q.where(PurchaseRequest.requested_by == member.get("staff_id"))
        rows = (await db.execute(q.order_by(PurchaseRequest.created_at.desc()))).scalars().all()
        result = []
        for r in rows:
            await db.refresh(r, ["items"])
            result.append(_req_dict(r))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_purchase_requests failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/purchase-requests", status_code=201)
async def create_purchase_request(body: RequestCreate, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        rec = PurchaseRequest(
            org_id=org_id, requested_by=member.get("staff_id"),
            title=body.title, justification=body.justification,
            supplier_id=body.supplier_id, estimated_total=Decimal(str(body.estimated_total)),
            currency=body.currency,
            urgency=body.urgency,
            budget_category=body.budget_category,
            is_template=body.is_template,
            template_name=body.template_name,
        )
        db.add(rec)
        await db.flush()
        for item in body.items:
            db.add(PurchaseRequestItem(
                purchase_request_id=rec.id, description=item.description,
                quantity=item.quantity, unit_price=Decimal(str(item.unit_price)),
                product_id=item.product_id,
            ))
        await db.commit()
        await db.refresh(rec, ["items"])
        return _req_dict(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_purchase_request failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/purchase-requests/{req_id}")
async def get_purchase_request(req_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        rec = (await db.execute(select(PurchaseRequest).where(PurchaseRequest.id == req_id, PurchaseRequest.org_id == org_id))).scalar_one_or_none()
        if not rec:
            raise HTTPException(status_code=404, detail="Not found")
        await db.refresh(rec, ["items"])
        return _req_dict(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_purchase_request failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/purchase-requests/{req_id}/approve", dependencies=_MANAGER_ONLY)
async def approve_purchase_request(req_id: str, body: ReviewBody, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        role = member.get("role", "MEMBER")
        if role not in ("OWNER", "ADMIN"):
            raise HTTPException(status_code=403, detail="Only managers can approve")
        rec = (await db.execute(select(PurchaseRequest).where(PurchaseRequest.id == req_id, PurchaseRequest.org_id == org_id))).scalar_one_or_none()
        if not rec:
            raise HTTPException(status_code=404, detail="Not found")
        if rec.status != "pending":
            raise HTTPException(status_code=409, detail="Already reviewed")
        rec.status = "approved"
        rec.reviewed_by = member.get("staff_id")
        rec.reviewed_at = datetime.now(timezone.utc)
        rec.review_note = body.note
        # Create draft PO
        await db.refresh(rec, ["items"])
        po = PurchaseOrder(org_id=org_id, supplier_id=rec.supplier_id, status="DRAFT")
        db.add(po)
        await db.flush()
        for item in rec.items:
            db.add(PurchaseOrderItem(
                purchase_order_id=po.id, product_id=item.product_id,
                quantity=item.quantity, unit_price=item.unit_price,
                line_total=item.unit_price * item.quantity,
            ))
        rec.purchase_order_id = po.id
        await db.commit()
        await db.refresh(rec, ["items"])
        return _req_dict(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"approve_purchase_request failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/purchase-requests/{req_id}/reject", dependencies=_MANAGER_ONLY)
async def reject_purchase_request(req_id: str, body: ReviewBody, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        role = member.get("role", "MEMBER")
        if role not in ("OWNER", "ADMIN"):
            raise HTTPException(status_code=403, detail="Only managers can reject")
        rec = (await db.execute(select(PurchaseRequest).where(PurchaseRequest.id == req_id, PurchaseRequest.org_id == org_id))).scalar_one_or_none()
        if not rec:
            raise HTTPException(status_code=404, detail="Not found")
        if rec.status != "pending":
            raise HTTPException(status_code=409, detail="Already reviewed")
        rec.status = "rejected"
        rec.reviewed_by = member.get("staff_id")
        rec.reviewed_at = datetime.now(timezone.utc)
        rec.review_note = body.note
        await db.commit()
        await db.refresh(rec, ["items"])
        return _req_dict(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"reject_purchase_request failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


def _req_dict(r: PurchaseRequest) -> dict:
    return {
        "id": str(r.id), "requested_by": str(r.requested_by),
        "supplier_id": str(r.supplier_id) if r.supplier_id else None,
        "title": r.title, "justification": r.justification,
        "estimated_total": float(r.estimated_total), "currency": r.currency,
        "status": r.status,
        "urgency": getattr(r, "urgency", "normal"),
        "budget_category": getattr(r, "budget_category", None),
        "budget_exceeded": getattr(r, "budget_exceeded", False),
        "is_template": getattr(r, "is_template", False),
        "template_name": getattr(r, "template_name", None),
        "reviewed_by": str(r.reviewed_by) if r.reviewed_by else None,
        "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        "review_note": r.review_note,
        "purchase_order_id": str(r.purchase_order_id) if r.purchase_order_id else None,
        "items": [{"id": str(i.id), "description": i.description, "quantity": i.quantity, "unit_price": float(i.unit_price), "product_id": str(i.product_id) if i.product_id else None} for i in (r.items or [])],
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/api/purchase-requests/report")
async def purchase_request_report(member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    """Spending summary: total submitted / approved / declined / approved value."""
    try:
        from sqlalchemy import func as _func
        org_id = member["org_id"]
        rows = (await db.execute(
            select(PurchaseRequest).where(PurchaseRequest.org_id == org_id, PurchaseRequest.is_template == False)  # noqa: E712
        )).scalars().all()
        total_submitted = len(rows)
        total_approved = sum(1 for r in rows if r.status == "approved")
        total_rejected = sum(1 for r in rows if r.status == "rejected")
        total_pending = sum(1 for r in rows if r.status == "pending")
        value_approved = float(sum(r.estimated_total for r in rows if r.status == "approved"))
        value_pending = float(sum(r.estimated_total for r in rows if r.status == "pending"))
        # by category
        by_category: dict = {}
        for r in rows:
            cat = getattr(r, "budget_category", None) or "Uncategorised"
            if cat not in by_category:
                by_category[cat] = {"count": 0, "value": 0.0}
            by_category[cat]["count"] += 1
            by_category[cat]["value"] += float(r.estimated_total)
        return {
            "total_submitted": total_submitted,
            "total_approved": total_approved,
            "total_rejected": total_rejected,
            "total_pending": total_pending,
            "value_approved": value_approved,
            "value_pending": value_pending,
            "by_category": by_category,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"purchase_request_report failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
