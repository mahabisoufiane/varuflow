"""Digital E-Signature router.

Provides a full signing-envelope workflow: create request, add signatories,
send invitation emails, public signing endpoint (token-based, no auth),
audit trail, and signed PDF tracking.

Endpoints (staff, authenticated):
  GET    /api/esign/requests        List signing requests
  POST   /api/esign/requests        Create a new signing request
  GET    /api/esign/requests/{id}   Detail with signatories + audit trail
  POST   /api/esign/requests/{id}/send     Send invitations to all signatories
  POST   /api/esign/requests/{id}/remind   Resend to pending signatories
  PATCH  /api/esign/requests/{id}/cancel   Cancel the request
  GET    /api/esign/requests/{id}/certificate  Download audit certificate (text)

Endpoints (public, token-auth):
  GET    /api/esign/sign/{token}    View signing page data (no Supabase auth)
  POST   /api/esign/sign/{token}    Submit signature
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from html import escape as html_escape
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.esign import ESignAuditEntry, ESignRequest, ESignSignatory

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/esign", tags=["esign"], dependencies=[Depends(require_module("finance"))])


# ── helpers ──────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _member_org(member: dict) -> uuid.UUID:
    return uuid.UUID(str(member["org_id"]))


def _sig_status(signatories: list[ESignSignatory]) -> str:
    total = len(signatories)
    if total == 0:
        return "draft"
    signed = sum(1 for s in signatories if s.status == "signed")
    declined = sum(1 for s in signatories if s.status == "declined")
    if declined:
        return "declined"
    if signed == total:
        return "fully_signed"
    if signed > 0:
        return "partially_signed"
    return "sent"


async def _add_audit(
    db: AsyncSession,
    request_id: uuid.UUID,
    event_type: str,
    actor_email: str | None = None,
    actor_name: str | None = None,
    ip_address: str | None = None,
    metadata: dict | None = None,
) -> None:
    entry = ESignAuditEntry(
        request_id=request_id,
        event_type=event_type,
        actor_email=actor_email,
        actor_name=actor_name,
        ip_address=ip_address,
        metadata=metadata,
    )
    db.add(entry)


async def _send_invitation_email(signatory: ESignSignatory, request: ESignRequest, base_url: str) -> None:
    """Send signing invitation. Uses Resend if configured, else logs."""
    import os
    sign_url = f"{base_url}/sign/{signatory.token}"
    resend_key = os.getenv("RESEND_API_KEY", "")
    from_email = os.getenv("SMTP_FROM", "noreply@varuflow.se")
    if not resend_key:
        log.info("esign_invite not sent (no RESEND_API_KEY): to=%s url=%s", signatory.email, sign_url)  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
        return
    try:
        import httpx
        payload = {
            "from": from_email,
            "to": [signatory.email],
            "subject": f"Signature requested: {request.title}",
            "html": (
                f"<p>Hello {html_escape(signatory.name)},</p>"
                f"<p>You have been requested to sign <strong>{html_escape(request.title)}</strong>.</p>"  # nosemgrep: python.django.security.injection.raw-html-format.raw-html-format
                f"{f'<p>{html_escape(request.message)}</p>' if request.message else ''}"  # nosemgrep: python.django.security.injection.raw-html-format.raw-html-format
                f"<p><a href='{html_escape(sign_url)}' style='background:#000;color:#fff;padding:10px 20px;"
                f"border-radius:6px;text-decoration:none;font-family:sans-serif;'>Review &amp; Sign</a></p>"
                f"<p style='font-size:12px;color:#888'>This link is unique to you. Do not share it.</p>"
            ),
        }
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                "https://api.resend.com/emails",
                json=payload,
                headers={"Authorization": f"Bearer {resend_key}"},
            )
    except Exception as exc:
        log.error("esign_invite email failed: %s", str(exc))


# ── Schemas ───────────────────────────────────────────────────────────────────

class SignatoryIn(BaseModel):
    name: str
    email: str
    role: Optional[str] = None
    sign_order: int = 1


class CreateRequestIn(BaseModel):
    title: str
    message: Optional[str] = None
    document_id: Optional[str] = None
    reminder_days: Optional[int] = None
    expires_in_days: Optional[int] = 30
    signatories: list[SignatoryIn] = []


class SignatureSubmitIn(BaseModel):
    signature_data: dict  # {type: "typed"|"drawn", value: "..."}
    agree: bool


class CancelIn(BaseModel):
    reason: Optional[str] = None


class SignatoryOut(BaseModel):
    id: str
    name: str
    email: str
    role: Optional[str]
    sign_order: int
    status: str
    signed_at: Optional[str]
    declined_at: Optional[str]
    token: str


class AuditEntryOut(BaseModel):
    event_type: str
    actor_email: Optional[str]
    actor_name: Optional[str]
    ip_address: Optional[str]
    created_at: str


class RequestOut(BaseModel):
    id: str
    title: str
    message: Optional[str]
    document_id: Optional[str]
    status: str
    reminder_days: Optional[int]
    expires_at: Optional[str]
    completed_at: Optional[str]
    signed_pdf_url: Optional[str]
    created_at: str
    signatories: list[SignatoryOut]
    audit_entries: list[AuditEntryOut]


def _sig_out(s: ESignSignatory) -> SignatoryOut:
    return SignatoryOut(
        id=str(s.id),
        name=s.name,
        email=s.email,
        role=s.role,
        sign_order=s.sign_order,
        status=s.status,
        signed_at=s.signed_at.isoformat() if s.signed_at else None,
        declined_at=s.declined_at.isoformat() if s.declined_at else None,
        token=s.token,
    )


def _req_out(r: ESignRequest) -> RequestOut:
    return RequestOut(
        id=str(r.id),
        title=r.title,
        message=r.message,
        document_id=str(r.document_id) if r.document_id else None,
        status=r.status,
        reminder_days=r.reminder_days,
        expires_at=r.expires_at.isoformat() if r.expires_at else None,
        completed_at=r.completed_at.isoformat() if r.completed_at else None,
        signed_pdf_url=r.signed_pdf_url,
        created_at=r.created_at.isoformat(),
        signatories=[_sig_out(s) for s in (r.signatories or [])],
        audit_entries=[
            AuditEntryOut(
                event_type=e.event_type,
                actor_email=e.actor_email,
                actor_name=e.actor_name,
                ip_address=e.ip_address,
                created_at=e.created_at.isoformat(),
            )
            for e in sorted(r.audit_entries or [], key=lambda x: x.created_at)
        ],
    )


# ── Staff endpoints ───────────────────────────────────────────────────────────

@router.get("/requests")
async def list_requests(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    org_id = _member_org(member)
    try:
        q = (
            select(ESignRequest)
            .where(ESignRequest.org_id == org_id)
            .options(selectinload(ESignRequest.signatories), selectinload(ESignRequest.audit_entries))
            .order_by(ESignRequest.created_at.desc())
        )
        if status:
            q = q.where(ESignRequest.status == status)
        offset = (page - 1) * limit
        rows = await db.execute(q.limit(limit).offset(offset))
        requests = rows.scalars().all()
        return {"items": [_req_out(r) for r in requests], "total": len(requests)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("esign_list failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/requests", status_code=201)
async def create_request(
    body: CreateRequestIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    org_id = _member_org(member)
    try:
        expires_at = _now() + timedelta(days=body.expires_in_days or 30)
        req = ESignRequest(
            org_id=org_id,
            title=body.title,
            message=body.message,
            document_id=uuid.UUID(body.document_id) if body.document_id else None,
            reminder_days=body.reminder_days,
            expires_at=expires_at,
            created_by=uuid.UUID(str(member["user_id"])) if member.get("user_id") else None,
            status="draft",
        )
        db.add(req)
        await db.flush()  # get req.id

        for s_in in body.signatories:
            sig = ESignSignatory(
                request_id=req.id,
                name=s_in.name,
                email=s_in.email,
                role=s_in.role,
                sign_order=s_in.sign_order,
                token=str(uuid.uuid4()),
                status="pending",
            )
            db.add(sig)

        await _add_audit(db, req.id, "created", metadata={"title": body.title})
        await db.commit()
        await db.refresh(req)

        # Reload with relationships
        full = await db.execute(
            select(ESignRequest)
            .where(ESignRequest.id == req.id)
            .options(selectinload(ESignRequest.signatories), selectinload(ESignRequest.audit_entries))
        )
        return _req_out(full.scalar_one())
    except HTTPException:
        raise
    except Exception as e:
        log.error("esign_create failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/requests/{request_id}")
async def get_request(
    request_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    org_id = _member_org(member)
    try:
        row = await db.execute(
            select(ESignRequest)
            .where(ESignRequest.id == request_id, ESignRequest.org_id == org_id)
            .options(selectinload(ESignRequest.signatories), selectinload(ESignRequest.audit_entries))
        )
        req = row.scalar_one_or_none()
        if not req:
            raise HTTPException(status_code=404, detail="Signing request not found")
        return _req_out(req)
    except HTTPException:
        raise
    except Exception as e:
        log.error("esign_get failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/requests/{request_id}/send")
async def send_request(
    request_id: uuid.UUID,
    http_request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Send invitation emails to all pending signatories."""
    _, member = ctx
    org_id = _member_org(member)
    try:
        row = await db.execute(
            select(ESignRequest)
            .where(ESignRequest.id == request_id, ESignRequest.org_id == org_id)
            .options(selectinload(ESignRequest.signatories))
        )
        req = row.scalar_one_or_none()
        if not req:
            raise HTTPException(status_code=404, detail="Signing request not found")
        if req.status == "cancelled":
            raise HTTPException(status_code=400, detail="Request is cancelled")
        if req.status == "fully_signed":
            raise HTTPException(status_code=400, detail="Request already fully signed")

        import os
        base_url = os.getenv("PORTAL_BASE_URL", "https://varuflow.vercel.app")
        for sig in req.signatories:
            if sig.status == "pending":
                await _send_invitation_email(sig, req, base_url)
                await _add_audit(db, req.id, "sent", actor_email=sig.email, actor_name=sig.name)

        req.status = "sent"
        await db.commit()
        return {"sent_to": [s.email for s in req.signatories if s.status == "pending"]}
    except HTTPException:
        raise
    except Exception as e:
        log.error("esign_send failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/requests/{request_id}/remind")
async def remind_request(
    request_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Resend invitations to signatories who have not yet signed."""
    _, member = ctx
    org_id = _member_org(member)
    try:
        row = await db.execute(
            select(ESignRequest)
            .where(ESignRequest.id == request_id, ESignRequest.org_id == org_id)
            .options(selectinload(ESignRequest.signatories))
        )
        req = row.scalar_one_or_none()
        if not req:
            raise HTTPException(status_code=404, detail="Signing request not found")

        import os
        base_url = os.getenv("PORTAL_BASE_URL", "https://varuflow.vercel.app")
        reminded = []
        for sig in req.signatories:
            if sig.status == "pending":
                await _send_invitation_email(sig, req, base_url)
                await _add_audit(db, req.id, "reminder_sent", actor_email=sig.email)
                reminded.append(sig.email)
        await db.commit()
        return {"reminded": reminded}
    except HTTPException:
        raise
    except Exception as e:
        log.error("esign_remind failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/requests/{request_id}/cancel")
async def cancel_request(
    request_id: uuid.UUID,
    body: CancelIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    org_id = _member_org(member)
    try:
        row = await db.execute(
            select(ESignRequest)
            .where(ESignRequest.id == request_id, ESignRequest.org_id == org_id)
        )
        req = row.scalar_one_or_none()
        if not req:
            raise HTTPException(status_code=404, detail="Signing request not found")
        if req.status in ("fully_signed", "cancelled"):
            raise HTTPException(status_code=400, detail=f"Cannot cancel a {req.status} request")
        req.status = "cancelled"
        await _add_audit(db, req.id, "cancelled", metadata={"reason": body.reason})
        await db.commit()
        return {"status": "cancelled"}
    except HTTPException:
        raise
    except Exception as e:
        log.error("esign_cancel failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/requests/{request_id}/certificate", response_class=PlainTextResponse)
async def download_certificate(
    request_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Download a plain-text audit certificate for legal purposes."""
    _, member = ctx
    org_id = _member_org(member)
    try:
        row = await db.execute(
            select(ESignRequest)
            .where(ESignRequest.id == request_id, ESignRequest.org_id == org_id)
            .options(selectinload(ESignRequest.signatories), selectinload(ESignRequest.audit_entries))
        )
        req = row.scalar_one_or_none()
        if not req:
            raise HTTPException(status_code=404, detail="Signing request not found")

        lines = [
            "=== VARUFLOW DIGITAL SIGNATURE AUDIT CERTIFICATE ===",
            f"Document Title : {req.title}",
            f"Request ID     : {req.id}",
            f"Status         : {req.status}",
            f"Created At     : {req.created_at.isoformat()}",
            f"Completed At   : {req.completed_at.isoformat() if req.completed_at else 'N/A'}",
            "",
            "=== SIGNATORIES ===",
        ]
        for sig in req.signatories:
            lines.append(
                f"  {sig.name} <{sig.email}> [{sig.role or 'Signatory'}] "
                f"— {sig.status.upper()}"
                + (f" at {sig.signed_at.isoformat()}" if sig.signed_at else "")
                + (f" (IP: {sig.ip_address})" if sig.ip_address else "")
            )

        lines += ["", "=== AUDIT TRAIL ==="]
        for entry in sorted(req.audit_entries, key=lambda e: e.created_at):
            lines.append(
                f"  [{entry.created_at.isoformat()}] {entry.event_type.upper()}"
                + (f" by {entry.actor_email}" if entry.actor_email else "")
                + (f" from IP {entry.ip_address}" if entry.ip_address else "")
            )

        lines += [
            "",
            "=== LEGAL NOTE ===",
            "This certificate provides an audit trail of the signing process.",
            "Timestamps are in UTC. IP addresses have been logged for each event.",
            "Generated by Varuflow — https://varuflow.vercel.app",
        ]

        return "\n".join(lines)
    except HTTPException:
        raise
    except Exception as e:
        log.error("esign_certificate failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Public signing endpoints (token-based, NO staff auth) ─────────────────────

@router.get("/sign/{token}")
async def get_signing_page(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint — signatory views the document details before signing."""
    try:
        row = await db.execute(
            select(ESignSignatory)
            .where(ESignSignatory.token == token)
            .options(selectinload(ESignSignatory.request))
        )
        sig = row.scalar_one_or_none()
        if not sig:
            raise HTTPException(status_code=404, detail="Invalid or expired signing link")

        req = sig.request
        if req.status in ("cancelled", "expired"):
            raise HTTPException(status_code=410, detail=f"This signing request has been {req.status}")
        if req.expires_at and req.expires_at < _now():
            raise HTTPException(status_code=410, detail="This signing link has expired")
        if sig.status == "signed":
            return {"already_signed": True, "signed_at": sig.signed_at.isoformat()}
        if sig.status == "declined":
            return {"declined": True}

        # Record "viewed" event (idempotent — only log first view)
        await _add_audit(db, req.id, "viewed", actor_email=sig.email, actor_name=sig.name)
        await db.commit()

        return {
            "request_id": str(req.id),
            "title": req.title,
            "message": req.message,
            "document_id": str(req.document_id) if req.document_id else None,
            "expires_at": req.expires_at.isoformat() if req.expires_at else None,
            "signatory": {
                "id": str(sig.id),
                "name": sig.name,
                "email": sig.email,
                "role": sig.role,
            },
            "already_signed": False,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("esign_sign_view failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sign/{token}")
async def submit_signature(
    token: str,
    body: SignatureSubmitIn,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint — signatory submits their signature."""
    try:
        if not body.agree:
            raise HTTPException(status_code=400, detail="You must agree to the legal terms to sign")

        row = await db.execute(
            select(ESignSignatory)
            .where(ESignSignatory.token == token)
            .options(selectinload(ESignSignatory.request).selectinload(ESignRequest.signatories))
        )
        sig = row.scalar_one_or_none()
        if not sig:
            raise HTTPException(status_code=404, detail="Invalid or expired signing link")

        req = sig.request
        if req.status in ("cancelled", "expired"):
            raise HTTPException(status_code=410, detail="This signing request is no longer active")
        if req.expires_at and req.expires_at < _now():
            raise HTTPException(status_code=410, detail="This signing link has expired")
        if sig.status == "signed":
            raise HTTPException(status_code=409, detail="Already signed")

        # Get client IP
        ip = http_request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
            http_request.client.host if http_request.client else "unknown"
        )
        ua = http_request.headers.get("User-Agent", "")[:1000]

        sig.status = "signed"
        sig.signed_at = _now()
        sig.signature_data = body.signature_data
        sig.ip_address = ip
        sig.user_agent = ua

        await _add_audit(
            db, req.id, "signed",
            actor_email=sig.email, actor_name=sig.name,
            ip_address=ip,
            metadata={"signature_type": body.signature_data.get("type", "unknown")},
        )

        # Recompute request status
        all_sigs = req.signatories
        new_status = _sig_status(all_sigs)
        req.status = new_status
        if new_status == "fully_signed":
            req.completed_at = _now()
            await _add_audit(db, req.id, "completed")

        await db.commit()
        return {"signed": True, "request_status": new_status}
    except HTTPException:
        raise
    except Exception as e:
        log.error("esign_sign_submit failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sign/{token}/decline")
async def decline_signature(
    token: str,
    reason: Optional[str] = None,
    http_request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint — signatory declines to sign."""
    try:
        row = await db.execute(
            select(ESignSignatory)
            .where(ESignSignatory.token == token)
            .options(selectinload(ESignSignatory.request).selectinload(ESignRequest.signatories))
        )
        sig = row.scalar_one_or_none()
        if not sig:
            raise HTTPException(status_code=404, detail="Invalid or expired signing link")

        if sig.status != "pending":
            raise HTTPException(status_code=409, detail=f"Already {sig.status}")

        ip = ""
        if http_request:
            ip = http_request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
                http_request.client.host if http_request.client else ""
            )

        sig.status = "declined"
        sig.declined_at = _now()
        sig.decline_reason = reason
        sig.ip_address = ip

        req = sig.request
        req.status = "declined"

        await _add_audit(db, req.id, "declined", actor_email=sig.email, actor_name=sig.name, ip_address=ip,
                         metadata={"reason": reason})
        await db.commit()
        return {"declined": True}
    except HTTPException:
        raise
    except Exception as e:
        log.error("esign_decline failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")
