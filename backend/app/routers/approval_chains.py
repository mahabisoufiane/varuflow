"""Approval Chains router — rule configuration, approval queue, escalation, delegates.

Endpoints:
  GET    /api/governance/rules                          list rules
  POST   /api/governance/rules                          create rule
  PATCH  /api/governance/rules/{id}                     update rule
  DELETE /api/governance/rules/{id}                     delete rule

  GET    /api/governance/approvals                      list requests
  GET    /api/governance/approvals/summary              counts + pending value
  POST   /api/governance/approvals/request              submit for approval
  POST   /api/governance/approvals/check                check if amount requires approval
  POST   /api/governance/approvals/{id}/approve         approve
  POST   /api/governance/approvals/{id}/reject          reject
  POST   /api/governance/approvals/{id}/escalate        manual escalate
  POST   /api/governance/approvals/escalate-overdue     batch escalate by rule threshold

  GET    /api/governance/delegates                      list delegates
  POST   /api/governance/delegates                      create delegate
  DELETE /api/governance/delegates/{id}                 remove delegate
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.governance import ApprovalDelegate, ApprovalRequest, ApprovalRule
from app.models.organization import OrgRole

logger = logging.getLogger(__name__)
router = APIRouter(tags=["approval-chains"])

_VALID_RESOURCE_TYPES = {"invoice", "expense", "purchase_order", "quote"}
_VALID_ROLES           = {"OWNER", "ADMIN"}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id

def _user_id(ctx: tuple) -> uuid.UUID:
    user, _ = ctx
    return user["user_id"]

def _email(ctx: tuple) -> str | None:
    user, _ = ctx
    return user.get("email")

def _role(ctx: tuple) -> str:
    _, member = ctx
    return member.role.value if hasattr(member.role, "value") else str(member.role)

def _require_admin(ctx: tuple) -> None:
    _, member = ctx
    if member.role not in (OrgRole.OWNER, OrgRole.ADMIN):
        raise HTTPException(status_code=403, detail="Admin or owner required")


async def _load_request(request_id: str, org_id: uuid.UUID, db: AsyncSession) -> ApprovalRequest:
    req = (await db.execute(
        select(ApprovalRequest).where(
            ApprovalRequest.id == uuid.UUID(request_id),
            ApprovalRequest.org_id == org_id,
        )
    )).scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return req


async def _send_notification(to_email: str, subject: str, body_html: str) -> None:
    """Fire-and-forget email via Resend. Silently skips if RESEND_API_KEY is missing."""
    if not getattr(settings, "RESEND_API_KEY", None):
        return
    try:
        payload = {
            "from": "approvals@varuflow.app",
            "to": [to_email],
            "subject": subject,
            "html": body_html,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                json=payload,
            )
    except Exception as exc:
        logger.warning(f"approval email failed: {exc}")


def _rule_dict(r: ApprovalRule) -> dict:
    return {
        "id": str(r.id), "resource_type": r.resource_type,
        "threshold_amount": float(r.threshold_amount), "currency": r.currency,
        "required_approver_role": r.required_approver_role,
        "description": r.description, "is_active": r.is_active,
        "escalation_days": r.escalation_days, "notify_email": r.notify_email,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _req_dict(r: ApprovalRequest) -> dict:
    return {
        "id": str(r.id), "resource_type": r.resource_type,
        "resource_id": str(r.resource_id), "resource_label": r.resource_label,
        "amount": float(r.amount) if r.amount else None,
        "currency": r.currency, "status": r.status,
        "requested_by": str(r.requested_by), "requested_by_email": r.requested_by_email,
        "requested_at": r.requested_at.isoformat() if r.requested_at else None,
        "reviewed_by": str(r.reviewed_by) if r.reviewed_by else None,
        "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        "reviewer_note": r.reviewer_note,
        "rule_id": str(r.rule_id) if r.rule_id else None,
        "escalated_at": r.escalated_at.isoformat() if r.escalated_at else None,
        "escalated_to_role": r.escalated_to_role,
    }


def _delegate_dict(d: ApprovalDelegate) -> dict:
    return {
        "id": str(d.id),
        "delegated_from_role": d.delegated_from_role,
        "delegated_to_user_id": str(d.delegated_to_user_id),
        "delegated_to_email": d.delegated_to_email,
        "valid_from": d.valid_from.isoformat(),
        "valid_until": d.valid_until.isoformat(),
        "note": d.note,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


async def _set_resource_approval_status(
    resource_type: str, resource_id: str, org_id: uuid.UUID, status: str,
    db: AsyncSession, extra: dict | None = None,
) -> None:
    """Update approval_status on the source resource after a decision."""
    params: dict = {"id": resource_id, "org_id": str(org_id), "status": status}
    if resource_type == "invoice":
        await db.execute(text(
            "UPDATE invoices SET approval_status = :status WHERE id = :id AND org_id = :org_id"
        ), params)
    elif resource_type == "expense":
        if status == "approved" and extra:
            await db.execute(text("""
                UPDATE expenses
                SET status = 'APPROVED', approved_by = :reviewer, approved_at = :now, review_note = :note
                WHERE id = :id AND org_id = :org_id
            """), {**params, **extra})
        elif status == "rejected":
            await db.execute(text("""
                UPDATE expenses SET status = 'REJECTED', review_note = :note WHERE id = :id AND org_id = :org_id
            """), {**params, "note": extra.get("note") if extra else None})
        else:
            await db.execute(text(
                "UPDATE expenses SET approval_required = true WHERE id = :id AND org_id = :org_id"
            ), params)
    elif resource_type == "purchase_order":
        await db.execute(text(
            "UPDATE purchase_orders SET approval_status = :status WHERE id = :id AND org_id = :org_id"
        ), params)
    elif resource_type == "quote":
        await db.execute(text(
            "UPDATE quotes SET approval_status = :status WHERE id = :id AND org_id = :org_id"
        ), params)


# ── Pydantic Models ───────────────────────────────────────────────────────────

class RuleCreate(BaseModel):
    resource_type: str
    threshold_amount: float
    currency: str = "SEK"
    required_approver_role: str = "OWNER"
    description: Optional[str] = None
    escalation_days: Optional[int] = Field(None, gt=0, le=365)
    notify_email: Optional[str] = Field(None, max_length=254)

class RuleUpdate(BaseModel):
    threshold_amount: Optional[float] = None
    currency: Optional[str] = None
    required_approver_role: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    escalation_days: Optional[int] = Field(None, gt=0, le=365)
    notify_email: Optional[str] = Field(None, max_length=254)

class RequestCreate(BaseModel):
    resource_type: str
    resource_id: str
    resource_label: Optional[str] = None
    amount: Optional[float] = None
    currency: str = "SEK"

class ReviewBody(BaseModel):
    reviewer_note: Optional[str] = None

class DelegateCreate(BaseModel):
    delegated_from_role: str
    delegated_to_user_id: uuid.UUID
    delegated_to_email: Optional[str] = Field(None, max_length=254)
    valid_from: date
    valid_until: date
    note: Optional[str] = Field(None, max_length=300)


# ── Rules CRUD ────────────────────────────────────────────────────────────────

@router.get("/api/governance/rules")
async def list_rules(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        rows = (await db.execute(
            select(ApprovalRule)
            .where(ApprovalRule.org_id == _org(ctx))
            .order_by(ApprovalRule.resource_type, ApprovalRule.threshold_amount)
        )).scalars().all()
        return [_rule_dict(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_rules failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/governance/rules", status_code=201)
async def create_rule(
    body: RuleCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _require_admin(ctx)
        org_id = _org(ctx)
        if body.resource_type not in _VALID_RESOURCE_TYPES:
            raise HTTPException(status_code=422, detail=f"resource_type must be one of {sorted(_VALID_RESOURCE_TYPES)}")
        if body.required_approver_role not in _VALID_ROLES:
            raise HTTPException(status_code=422, detail=f"required_approver_role must be one of {_VALID_ROLES}")
        rule = ApprovalRule(
            org_id=org_id,
            resource_type=body.resource_type,
            threshold_amount=Decimal(str(body.threshold_amount)),
            currency=body.currency.upper(),
            required_approver_role=body.required_approver_role,
            description=body.description,
            escalation_days=body.escalation_days,
            notify_email=body.notify_email,
            created_by=_user_id(ctx),
        )
        db.add(rule)
        await db.commit()
        await db.refresh(rule)
        return _rule_dict(rule)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_rule failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/governance/rules/{rule_id}")
async def update_rule(
    rule_id: str,
    body: RuleUpdate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _require_admin(ctx)
        org_id = _org(ctx)
        rule = (await db.execute(
            select(ApprovalRule).where(
                ApprovalRule.id == uuid.UUID(rule_id), ApprovalRule.org_id == org_id
            )
        )).scalar_one_or_none()
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        data = body.model_dump(exclude_unset=True)
        if "threshold_amount" in data:
            data["threshold_amount"] = Decimal(str(data["threshold_amount"]))
        if "currency" in data:
            data["currency"] = data["currency"].upper()
        if "required_approver_role" in data and data["required_approver_role"] not in _VALID_ROLES:
            raise HTTPException(status_code=422, detail=f"required_approver_role must be one of {_VALID_ROLES}")
        for field, val in data.items():
            setattr(rule, field, val)
        await db.commit()
        await db.refresh(rule)
        return _rule_dict(rule)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_rule failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/governance/rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: str,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _require_admin(ctx)
        org_id = _org(ctx)
        rule = (await db.execute(
            select(ApprovalRule).where(
                ApprovalRule.id == uuid.UUID(rule_id), ApprovalRule.org_id == org_id
            )
        )).scalar_one_or_none()
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        await db.delete(rule)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_rule failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Approval Requests ─────────────────────────────────────────────────────────

@router.get("/api/governance/approvals/summary")
async def approvals_summary(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Quick counts for the dashboard badge."""
    try:
        org_id = _org(ctx)
        result = await db.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'pending')  AS pending,
                COUNT(*) FILTER (WHERE status = 'approved') AS approved,
                COUNT(*) FILTER (WHERE status = 'rejected') AS rejected,
                COUNT(*) FILTER (WHERE status = 'pending' AND escalated_at IS NOT NULL) AS escalated,
                COALESCE(SUM(amount) FILTER (WHERE status = 'pending'), 0) AS pending_amount
            FROM approval_requests
            WHERE org_id = :org_id
        """), {"org_id": str(org_id)})
        r = result.fetchone()
        return {
            "pending": r.pending, "approved": r.approved,
            "rejected": r.rejected, "escalated": r.escalated,
            "pending_amount": float(r.pending_amount or 0),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"approvals_summary failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/governance/approvals")
async def list_approvals(
    status: Optional[str] = None,
    resource_type: Optional[str] = None,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org(ctx)
        q = select(ApprovalRequest).where(ApprovalRequest.org_id == org_id)
        if status:
            q = q.where(ApprovalRequest.status == status)
        if resource_type:
            q = q.where(ApprovalRequest.resource_type == resource_type)
        rows = (await db.execute(q.order_by(ApprovalRequest.requested_at.desc()).limit(200))).scalars().all()
        return [_req_dict(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_approvals failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/governance/approvals/request", status_code=201)
async def create_approval_request(
    body: RequestCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a resource for approval. Finds the highest-threshold matching active rule,
    creates an ApprovalRequest, marks the source resource, and notifies the approver
    if the rule carries a notify_email.
    """
    try:
        org_id = _org(ctx)
        if body.resource_type not in _VALID_RESOURCE_TYPES:
            raise HTTPException(status_code=422, detail="Invalid resource_type")

        amount = Decimal(str(body.amount)) if body.amount else Decimal("0")

        # Find the highest matching rule (multi-level: picks the strictest tier)
        rule = (await db.execute(
            select(ApprovalRule).where(
                ApprovalRule.org_id == org_id,
                ApprovalRule.resource_type == body.resource_type,
                ApprovalRule.is_active == True,         # noqa
                ApprovalRule.threshold_amount <= amount,
            ).order_by(ApprovalRule.threshold_amount.desc()).limit(1)
        )).scalar_one_or_none()

        req = ApprovalRequest(
            org_id=org_id,
            rule_id=rule.id if rule else None,
            resource_type=body.resource_type,
            resource_id=uuid.UUID(body.resource_id),
            resource_label=body.resource_label,
            amount=amount if amount > 0 else None,
            currency=body.currency,
            requested_by=_user_id(ctx),
            requested_by_email=_email(ctx),
            status="pending",
        )
        db.add(req)

        # Mark source resource as pending approval
        await _set_resource_approval_status(
            body.resource_type, body.resource_id, org_id, "pending", db
        )

        await db.commit()
        await db.refresh(req)

        # Email the approver role if rule has notify_email (e.g. CEO notification)
        if rule and rule.notify_email:
            label = body.resource_label or body.resource_id
            amt_str = f"{float(amount):,.2f} {body.currency}" if amount else ""
            asyncio.create_task(_send_notification(
                to_email=rule.notify_email,
                subject=f"[Varuflow] Approval needed: {body.resource_type} {label}",
                body_html=f"""
                <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
                  <h2 style="color:#1a2332">Approval required</h2>
                  <p>A <strong>{body.resource_type.replace('_',' ')}</strong> requires your approval.</p>
                  <table style="width:100%;border-collapse:collapse;font-size:14px;margin:16px 0">
                    <tr><td style="padding:6px;color:#6b7280">Reference</td>
                        <td style="padding:6px;font-weight:600">{label}</td></tr>
                    <tr><td style="padding:6px;color:#6b7280">Amount</td>
                        <td style="padding:6px;font-weight:600">{amt_str}</td></tr>
                    <tr><td style="padding:6px;color:#6b7280">Submitted by</td>
                        <td style="padding:6px">{_email(ctx) or 'unknown'}</td></tr>
                    <tr><td style="padding:6px;color:#6b7280">Rule</td>
                        <td style="padding:6px">{rule.description or rule.required_approver_role}</td></tr>
                  </table>
                  <p><a href="{getattr(settings,'FRONTEND_URL','https://varuflow.vercel.app')}/en/governance/approvals"
                       style="background:#1a2332;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600">
                    Review in Varuflow
                  </a></p>
                </div>
                """,
            ))

        return _req_dict(req)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_approval_request failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/governance/approvals/check")
async def check_approval_required(
    body: RequestCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return whether a given resource_type + amount would require approval."""
    try:
        org_id = _org(ctx)
        amount = Decimal(str(body.amount)) if body.amount else Decimal("0")
        rule = (await db.execute(
            select(ApprovalRule).where(
                ApprovalRule.org_id == org_id,
                ApprovalRule.resource_type == body.resource_type,
                ApprovalRule.is_active == True,         # noqa
                ApprovalRule.threshold_amount <= amount,
            ).limit(1)
        )).scalar_one_or_none()
        return {"requires_approval": rule is not None, "rule": _rule_dict(rule) if rule else None}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"check_approval failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/governance/approvals/{request_id}/approve")
async def approve_request(
    request_id: str,
    body: ReviewBody,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org(ctx)
        req = await _load_request(request_id, org_id, db)

        if req.status != "pending":
            raise HTTPException(status_code=409, detail="Request is not pending")

        now = datetime.now(timezone.utc)
        req.status = "approved"
        req.reviewed_by = _user_id(ctx)
        req.reviewed_at = now
        req.reviewer_note = body.reviewer_note

        extra = {"reviewer": str(_user_id(ctx)), "now": now, "note": body.reviewer_note}
        await _set_resource_approval_status(
            req.resource_type, str(req.resource_id), org_id, "approved", db, extra
        )

        await db.commit()
        await db.refresh(req)

        # Email the submitter
        if req.requested_by_email:
            label = req.resource_label or str(req.resource_id)
            asyncio.create_task(_send_notification(
                to_email=req.requested_by_email,
                subject=f"[Varuflow] Approved: {req.resource_type} {label}",
                body_html=f"""
                <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
                  <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:12px 16px;margin-bottom:20px">
                    <strong style="color:#16a34a">✓ Approved</strong>
                  </div>
                  <p>Your <strong>{req.resource_type.replace('_',' ')}</strong> <strong>{label}</strong>
                     has been <strong style="color:#16a34a">approved</strong>.</p>
                  {f'<p style="color:#6b7280;font-style:italic">Note: {body.reviewer_note}</p>' if body.reviewer_note else ''}
                </div>
                """,
            ))

        return _req_dict(req)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"approve_request failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/governance/approvals/{request_id}/reject")
async def reject_request(
    request_id: str,
    body: ReviewBody,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org(ctx)
        req = await _load_request(request_id, org_id, db)

        if req.status != "pending":
            raise HTTPException(status_code=409, detail="Request is not pending")

        now = datetime.now(timezone.utc)
        req.status = "rejected"
        req.reviewed_by = _user_id(ctx)
        req.reviewed_at = now
        req.reviewer_note = body.reviewer_note

        extra = {"note": body.reviewer_note}
        await _set_resource_approval_status(
            req.resource_type, str(req.resource_id), org_id, "rejected", db, extra
        )

        await db.commit()
        await db.refresh(req)

        # Email the submitter
        if req.requested_by_email:
            label = req.resource_label or str(req.resource_id)
            asyncio.create_task(_send_notification(
                to_email=req.requested_by_email,
                subject=f"[Varuflow] Rejected: {req.resource_type} {label}",
                body_html=f"""
                <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
                  <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:12px 16px;margin-bottom:20px">
                    <strong style="color:#dc2626">✗ Rejected</strong>
                  </div>
                  <p>Your <strong>{req.resource_type.replace('_',' ')}</strong> <strong>{label}</strong>
                     has been <strong style="color:#dc2626">rejected</strong>.</p>
                  {f'<p style="color:#6b7280;font-style:italic">Reason: {body.reviewer_note}</p>' if body.reviewer_note else ''}
                  <p>Please contact your manager if you believe this is in error.</p>
                </div>
                """,
            ))

        return _req_dict(req)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"reject_request failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/governance/approvals/{request_id}/escalate")
async def escalate_request(
    request_id: str,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Manually escalate a pending request to OWNER level."""
    try:
        _require_admin(ctx)
        org_id = _org(ctx)
        req = await _load_request(request_id, org_id, db)

        if req.status != "pending":
            raise HTTPException(status_code=409, detail="Only pending requests can be escalated")

        now = datetime.now(timezone.utc)
        req.escalated_at = now
        req.escalated_to_role = "OWNER"

        await db.commit()
        await db.refresh(req)
        return _req_dict(req)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"escalate_request failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/governance/approvals/escalate-overdue")
async def escalate_overdue(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """
    Batch-escalate all pending requests that have exceeded the rule's escalation_days
    threshold without a decision. Returns the count of requests escalated.
    """
    try:
        _require_admin(ctx)
        org_id = _org(ctx)
        now = datetime.now(timezone.utc)

        # Load pending, non-yet-escalated requests with their rules
        rows = (await db.execute(
            select(ApprovalRequest, ApprovalRule)
            .join(ApprovalRule, ApprovalRequest.rule_id == ApprovalRule.id, isouter=True)
            .where(
                ApprovalRequest.org_id == org_id,
                ApprovalRequest.status == "pending",
                ApprovalRequest.escalated_at == None,   # noqa
            )
        )).all()

        escalated = 0
        for req, rule in rows:
            if rule is None or rule.escalation_days is None:
                continue
            age_days = (now - req.requested_at).days
            if age_days >= rule.escalation_days:
                req.escalated_at = now
                req.escalated_to_role = "OWNER"
                escalated += 1

        await db.commit()
        return {"escalated": escalated}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"escalate_overdue failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Delegates ─────────────────────────────────────────────────────────────────

@router.get("/api/governance/delegates")
async def list_delegates(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org(ctx)
        rows = (await db.execute(
            select(ApprovalDelegate)
            .where(ApprovalDelegate.org_id == org_id)
            .order_by(ApprovalDelegate.valid_from.desc())
        )).scalars().all()
        return [_delegate_dict(d) for d in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_delegates failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/governance/delegates", status_code=201)
async def create_delegate(
    body: DelegateCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _require_admin(ctx)
        org_id = _org(ctx)
        if body.delegated_from_role not in _VALID_ROLES:
            raise HTTPException(status_code=422, detail="Invalid delegated_from_role")
        if body.valid_until < body.valid_from:
            raise HTTPException(status_code=422, detail="valid_until must be after valid_from")
        delegate = ApprovalDelegate(
            org_id=org_id,
            delegated_from_role=body.delegated_from_role,
            delegated_to_user_id=body.delegated_to_user_id,
            delegated_to_email=body.delegated_to_email,
            valid_from=body.valid_from,
            valid_until=body.valid_until,
            note=body.note,
            created_by=_user_id(ctx),
        )
        db.add(delegate)
        await db.commit()
        await db.refresh(delegate)
        return _delegate_dict(delegate)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_delegate failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/governance/delegates/{delegate_id}", status_code=204)
async def delete_delegate(
    delegate_id: str,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _require_admin(ctx)
        org_id = _org(ctx)
        d = (await db.execute(
            select(ApprovalDelegate).where(
                ApprovalDelegate.id == uuid.UUID(delegate_id),
                ApprovalDelegate.org_id == org_id,
            )
        )).scalar_one_or_none()
        if not d:
            raise HTTPException(status_code=404, detail="Delegate not found")
        await db.delete(d)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_delegate failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
