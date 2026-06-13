"""Email templates router.

GET  /api/email-templates              — list templates (filter by category)
POST /api/email-templates              — create template
GET  /api/email-templates/{id}         — detail
PATCH /api/email-templates/{id}        — update
DELETE /api/email-templates/{id}       — delete (not system templates)
POST /api/email-templates/{id}/revise  — create new version (bumps version, links parent_id)
POST /api/email-templates/{id}/send    — send to recipient, log in email_template_sends
GET  /api/email-templates/sends        — list send history
GET  /api/email-templates/track/{tracking_id}/open — pixel tracking (open event)
"""
import logging
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.email_templates import EmailTemplate, EmailTemplateSend

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/email-templates", tags=["email_templates"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class TemplateCreate(BaseModel):
    name: str
    subject: str
    body_html: str
    category: str = "general"
    variables: dict | None = None


class TemplatePatch(BaseModel):
    name: str | None = None
    subject: str | None = None
    body_html: str | None = None
    category: str | None = None
    variables: dict | None = None
    is_active: bool | None = None


class SendIn(BaseModel):
    to_email: str
    subject: str | None = None   # override; defaults to template subject
    variables: dict | None = None  # substitution values
    ref_type: str | None = None
    ref_id: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tpl_out(t: EmailTemplate) -> dict:
    return {
        "id": str(t.id),
        "org_id": str(t.org_id),
        "parent_id": str(t.parent_id) if t.parent_id else None,
        "name": t.name,
        "subject": t.subject,
        "body_html": t.body_html,
        "category": t.category,
        "variables": t.variables,
        "is_system": t.is_system,
        "is_active": t.is_active,
        "version": t.version,
        "created_by": str(t.created_by) if t.created_by else None,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
    }


def _render(text: str, variables: dict | None) -> str:
    """Simple {{variable}} substitution."""
    if not variables:
        return text
    for k, v in variables.items():
        text = text.replace(f"{{{{{k}}}}}", str(v))
    return text


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_templates(
    category: str | None = None,
    is_active: bool | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(EmailTemplate).where(EmailTemplate.org_id == org_id)
        if category:
            q = q.where(EmailTemplate.category == category)
        if is_active is not None:
            q = q.where(EmailTemplate.is_active == is_active)
        q = q.order_by(EmailTemplate.category, EmailTemplate.name)
        rows = (await db.execute(q)).scalars().all()
        return [_tpl_out(t) for t in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_templates failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_template(
    body: TemplateCreate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        t = EmailTemplate(
            org_id=org_id,
            name=body.name,
            subject=body.subject,
            body_html=body.body_html,
            category=body.category,
            variables=body.variables,
            created_by=member.get("staff_id"),
        )
        db.add(t)
        await db.commit()
        await db.refresh(t)
        return _tpl_out(t)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_template failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/sends")
async def list_sends(
    template_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(EmailTemplateSend).where(EmailTemplateSend.org_id == org_id)
        if template_id:
            q = q.where(EmailTemplateSend.template_id == uuid.UUID(template_id))
        q = q.order_by(EmailTemplateSend.sent_at.desc()).limit(limit).offset(offset)
        rows = (await db.execute(q)).scalars().all()
        return [
            {
                "id": str(s.id),
                "template_id": str(s.template_id) if s.template_id else None,
                "to_email": s.to_email,
                "subject": s.subject,
                "ref_type": s.ref_type,
                "ref_id": str(s.ref_id) if s.ref_id else None,
                "sent_at": s.sent_at.isoformat(),
                "opened_at": s.opened_at.isoformat() if s.opened_at else None,
                "clicked_at": s.clicked_at.isoformat() if s.clicked_at else None,
                "tracking_id": s.tracking_id,
            }
            for s in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_sends failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{template_id}")
async def get_template(
    template_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        t = (await db.execute(
            select(EmailTemplate).where(
                EmailTemplate.id == uuid.UUID(template_id),
                EmailTemplate.org_id == org_id,
            )
        )).scalar_one_or_none()
        if not t:
            raise HTTPException(status_code=404, detail="Template not found")
        return _tpl_out(t)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_template failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{template_id}")
async def update_template(
    template_id: str,
    body: TemplatePatch,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        t = (await db.execute(
            select(EmailTemplate).where(
                EmailTemplate.id == uuid.UUID(template_id),
                EmailTemplate.org_id == org_id,
            )
        )).scalar_one_or_none()
        if not t:
            raise HTTPException(status_code=404, detail="Template not found")
        if t.is_system:
            raise HTTPException(status_code=403, detail="System templates cannot be modified")
        for field, val in body.model_dump(exclude_unset=True).items():
            setattr(t, field, val)
        t.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return _tpl_out(t)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_template failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        t = (await db.execute(
            select(EmailTemplate).where(
                EmailTemplate.id == uuid.UUID(template_id),
                EmailTemplate.org_id == org_id,
            )
        )).scalar_one_or_none()
        if not t:
            raise HTTPException(status_code=404, detail="Template not found")
        if t.is_system:
            raise HTTPException(status_code=403, detail="System templates cannot be deleted")
        await db.delete(t)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_template failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{template_id}/revise", status_code=201)
async def revise_template(
    template_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Create a new version of the template, archiving the current one."""
    try:
        org_id = member["org_id"]
        parent = (await db.execute(
            select(EmailTemplate).where(
                EmailTemplate.id == uuid.UUID(template_id),
                EmailTemplate.org_id == org_id,
            )
        )).scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=404, detail="Template not found")
        # Archive the old version
        parent.is_active = False
        parent.updated_at = datetime.now(timezone.utc)
        # New version
        new_t = EmailTemplate(
            org_id=org_id,
            parent_id=parent.id,
            name=parent.name,
            subject=parent.subject,
            body_html=parent.body_html,
            category=parent.category,
            variables=parent.variables,
            version=parent.version + 1,
            created_by=member.get("staff_id"),
        )
        db.add(new_t)
        await db.commit()
        await db.refresh(new_t)
        return _tpl_out(new_t)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("revise_template failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{template_id}/send", status_code=201)
async def send_template(
    template_id: str,
    body: SendIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Log a send event (actual email delivery is done by Resend/SMTP in a service layer)."""
    try:
        org_id = member["org_id"]
        t = (await db.execute(
            select(EmailTemplate).where(
                EmailTemplate.id == uuid.UUID(template_id),
                EmailTemplate.org_id == org_id,
            )
        )).scalar_one_or_none()
        if not t:
            raise HTTPException(status_code=404, detail="Template not found")

        rendered_subject = _render(body.subject or t.subject, body.variables)
        tracking_id = secrets.token_urlsafe(16)

        send = EmailTemplateSend(
            template_id=t.id,
            org_id=org_id,
            to_email=body.to_email,
            subject=rendered_subject,
            ref_type=body.ref_type,
            ref_id=uuid.UUID(body.ref_id) if body.ref_id else None,
            tracking_id=tracking_id,
        )
        db.add(send)
        await db.commit()
        await db.refresh(send)
        return {
            "id": str(send.id),
            "template_id": str(t.id),
            "to_email": send.to_email,
            "subject": send.subject,
            "tracking_id": tracking_id,
            "sent_at": send.sent_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("send_template failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/track/{tracking_id}/open")
async def track_open(tracking_id: str, db: AsyncSession = Depends(get_db)):
    """Pixel tracking endpoint — record open event, return 1x1 transparent GIF."""
    try:
        send = (await db.execute(
            select(EmailTemplateSend).where(EmailTemplateSend.tracking_id == tracking_id)
        )).scalar_one_or_none()
        if send and not send.opened_at:
            send.opened_at = datetime.now(timezone.utc)
            await db.commit()
    except Exception:
        pass  # Tracking failure must not break the user experience

    from fastapi.responses import Response
    # 1×1 transparent GIF
    gif = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    return Response(content=gif, media_type="image/gif", headers={"Cache-Control": "no-store"})
