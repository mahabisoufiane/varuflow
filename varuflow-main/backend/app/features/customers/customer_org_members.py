"""Customer org members and buyer order approvals — Sprint 10.

Endpoints under ``/api/customer-org``:

    GET    /{customer_id}/members             list members
    POST   /{customer_id}/members             invite member
    PATCH  /{customer_id}/members/{member_id} update role/is_active
    DELETE /{customer_id}/members/{member_id} deactivate
    GET    /{customer_id}/approvals           list approval rows
    POST   /approvals                         create approval request
    POST   /approvals/{id}/approve            approve
    POST   /approvals/{id}/reject             reject
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from .customer_org_member import BuyerOrderApproval, CustomerOrgMember
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/customer-org", tags=["customer-org"], dependencies=[Depends(require_module("invoicing"))])
logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────────────

class MemberInvite(BaseModel):
    member_email: EmailStr
    member_name: str | None = None
    role: str = "requester"


class MemberUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    member_name: str | None = None


class MemberOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    member_email: str
    member_name: str | None
    role: str
    is_active: bool
    invited_at: datetime | None
    joined_at: datetime | None
    created_at: datetime


class ApprovalCreate(BaseModel):
    buyer_po_id: uuid.UUID
    requested_by_member_id: uuid.UUID | None = None


class ApprovalReview(BaseModel):
    reviewed_by_member_id: uuid.UUID | None = None
    notes: str | None = None


class ApprovalOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    buyer_po_id: uuid.UUID
    requested_by_member_id: uuid.UUID | None
    status: str
    reviewed_by_member_id: uuid.UUID | None
    reviewed_at: datetime | None
    notes: str | None
    created_at: datetime


def _member_to_out(row: CustomerOrgMember) -> MemberOut:
    return MemberOut(
        id=row.id,
        org_id=row.org_id,
        customer_id=row.customer_id,
        member_email=row.member_email,
        member_name=row.member_name,
        role=row.role,
        is_active=row.is_active,
        invited_at=row.invited_at,
        joined_at=row.joined_at,
        created_at=row.created_at,
    )


def _approval_to_out(row: BuyerOrderApproval) -> ApprovalOut:
    return ApprovalOut(
        id=row.id,
        org_id=row.org_id,
        buyer_po_id=row.buyer_po_id,
        requested_by_member_id=row.requested_by_member_id,
        status=row.status,
        reviewed_by_member_id=row.reviewed_by_member_id,
        reviewed_at=row.reviewed_at,
        notes=row.notes,
        created_at=row.created_at,
    )


async def _load_member(
    db: AsyncSession, *, member_id: uuid.UUID, org_id: uuid.UUID,
) -> CustomerOrgMember:
    row = await db.get(CustomerOrgMember, member_id)
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Member not found")
    return row


async def _load_approval(
    db: AsyncSession, *, approval_id: uuid.UUID, org_id: uuid.UUID,
) -> BuyerOrderApproval:
    row = await db.get(BuyerOrderApproval, approval_id)
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Approval not found")
    return row


# ── Members endpoints ─────────────────────────────────────────────────────────

@router.get("/{customer_id}/members", response_model=list[MemberOut])
async def list_members(
    customer_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        stmt = select(CustomerOrgMember).where(
            CustomerOrgMember.org_id == member.org_id,
            CustomerOrgMember.customer_id == customer_id,
        ).order_by(CustomerOrgMember.created_at)
        rows = (await db.scalars(stmt)).all()
        return [_member_to_out(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_members failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{customer_id}/members", response_model=MemberOut, status_code=201)
async def invite_member(
    customer_id: uuid.UUID,
    body: MemberInvite,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        row = CustomerOrgMember(
            org_id=member.org_id,
            customer_id=customer_id,
            member_email=str(body.member_email),
            member_name=body.member_name,
            role=body.role,
            invitation_token=secrets.token_urlsafe(32),
            invited_at=datetime.now(tz=timezone.utc),
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _member_to_out(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"invite_member failed: {str(e)}", extra={"org_id": str(member.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{customer_id}/members/{member_id}", response_model=MemberOut)
async def update_member(
    customer_id: uuid.UUID,
    member_id: uuid.UUID,
    body: MemberUpdate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        row = await _load_member(db, member_id=member_id, org_id=member.org_id)
        if row.customer_id != customer_id:
            raise HTTPException(status_code=404, detail="Member not found")
        for field, val in body.model_dump(exclude_unset=True).items():
            setattr(row, field, val)
        await db.commit()
        await db.refresh(row)
        return _member_to_out(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_member failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{customer_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_member(
    customer_id: uuid.UUID,
    member_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        row = await _load_member(db, member_id=member_id, org_id=member.org_id)
        if row.customer_id != customer_id:
            raise HTTPException(status_code=404, detail="Member not found")
        row.is_active = False
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"deactivate_member failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Approvals endpoints ───────────────────────────────────────────────────────

@router.get("/{customer_id}/approvals", response_model=list[ApprovalOut])
async def list_approvals(
    customer_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        from app.features.purchases.buyer_purchase_order import BuyerPurchaseOrder
        po_ids_stmt = select(BuyerPurchaseOrder.id).where(
            BuyerPurchaseOrder.org_id == member.org_id,
            BuyerPurchaseOrder.customer_id == customer_id,
        )
        stmt = select(BuyerOrderApproval).where(
            BuyerOrderApproval.org_id == member.org_id,
            BuyerOrderApproval.buyer_po_id.in_(po_ids_stmt),
        ).order_by(BuyerOrderApproval.created_at.desc())
        rows = (await db.scalars(stmt)).all()
        return [_approval_to_out(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_approvals failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/approvals", response_model=ApprovalOut, status_code=201)
async def create_approval(
    body: ApprovalCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        row = BuyerOrderApproval(
            org_id=member.org_id,
            buyer_po_id=body.buyer_po_id,
            requested_by_member_id=body.requested_by_member_id,
            status="pending",
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _approval_to_out(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_approval failed: {str(e)}", extra={"org_id": str(member.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalOut)
async def approve_order(
    approval_id: uuid.UUID,
    body: ApprovalReview,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        row = await _load_approval(db, approval_id=approval_id, org_id=member.org_id)
        row.status = "approved"
        row.reviewed_by_member_id = body.reviewed_by_member_id
        row.reviewed_at = datetime.now(tz=timezone.utc)
        row.notes = body.notes
        await db.commit()
        await db.refresh(row)
        return _approval_to_out(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"approve_order failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalOut)
async def reject_order(
    approval_id: uuid.UUID,
    body: ApprovalReview,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        row = await _load_approval(db, approval_id=approval_id, org_id=member.org_id)
        row.status = "rejected"
        row.reviewed_by_member_id = body.reviewed_by_member_id
        row.reviewed_at = datetime.now(tz=timezone.utc)
        row.notes = body.notes
        await db.commit()
        await db.refresh(row)
        return _approval_to_out(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"reject_order failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
