"""Lead form router: admin CRUD + public form submission."""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.lead_forms import LeadForm, LeadFormSubmission

log = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_module("crm"))])

_VALID_SLUG = re.compile(r"^[a-z0-9-]{2,80}$")


def _form_out(f: LeadForm) -> dict:
    return {
        "id": str(f.id),
        "slug": f.slug,
        "title": f.title,
        "description": f.description,
        "fields": f.fields,
        "redirect_url": f.redirect_url,
        "notify_email": f.notify_email,
        "is_active": f.is_active,
        "created_at": f.created_at.isoformat(),
        "updated_at": f.updated_at.isoformat(),
    }


def _submission_out(s: LeadFormSubmission) -> dict:
    return {
        "id": str(s.id),
        "form_id": str(s.form_id),
        "data": s.data,
        "submitter_email": s.submitter_email,
        "submitter_name": s.submitter_name,
        "converted_to_deal_id": str(s.converted_to_deal_id) if s.converted_to_deal_id else None,
        "created_at": s.created_at.isoformat(),
    }


# ── Admin endpoints (auth required) ─────────────────────────────────────────

class LeadFormCreate(BaseModel):
    title: str
    slug: Optional[str] = None
    description: Optional[str] = None
    fields: list[Any] = []
    redirect_url: Optional[str] = None
    notify_email: Optional[str] = None
    is_active: bool = True


class LeadFormUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    fields: Optional[list[Any]] = None
    redirect_url: Optional[str] = None
    notify_email: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/api/crm/lead-forms")
async def list_forms(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        result = await db.execute(
            select(LeadForm).where(LeadForm.org_id == org_id).order_by(LeadForm.created_at.desc())
        )
        forms = result.scalars().all()
        return [_form_out(f) for f in forms]
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_forms failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/crm/lead-forms", status_code=201)
async def create_form(
    body: LeadFormCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        slug = body.slug or re.sub(r"[^a-z0-9-]", "-", body.title.lower())[:60]
        if not _VALID_SLUG.match(slug):
            raise HTTPException(status_code=422, detail="Invalid slug")
        # Check uniqueness
        existing = await db.execute(select(LeadForm).where(LeadForm.slug == slug))
        if existing.scalars().first():
            slug = f"{slug}-{str(uuid.uuid4())[:8]}"
        form = LeadForm(
            id=uuid.uuid4(),
            org_id=org_id,
            slug=slug,
            title=body.title,
            description=body.description,
            fields=body.fields,
            redirect_url=body.redirect_url,
            notify_email=body.notify_email,
            is_active=body.is_active,
        )
        db.add(form)
        await db.commit()
        await db.refresh(form)
        return _form_out(form)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_form failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/crm/lead-forms/{form_id}")
async def update_form(
    form_id: uuid.UUID,
    body: LeadFormUpdate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        result = await db.execute(
            select(LeadForm).where(and_(LeadForm.id == form_id, LeadForm.org_id == org_id))
        )
        form = result.scalars().first()
        if not form:
            raise HTTPException(status_code=404, detail="Form not found")
        if body.title is not None:
            form.title = body.title
        if body.description is not None:
            form.description = body.description
        if body.fields is not None:
            form.fields = body.fields
        if body.redirect_url is not None:
            form.redirect_url = body.redirect_url
        if body.notify_email is not None:
            form.notify_email = body.notify_email
        if body.is_active is not None:
            form.is_active = body.is_active
        await db.commit()
        await db.refresh(form)
        return _form_out(form)
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_form failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/crm/lead-forms/{form_id}", status_code=204)
async def delete_form(
    form_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        result = await db.execute(
            select(LeadForm).where(and_(LeadForm.id == form_id, LeadForm.org_id == org_id))
        )
        form = result.scalars().first()
        if not form:
            raise HTTPException(status_code=404, detail="Form not found")
        await db.delete(form)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_form failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/crm/lead-forms/{form_id}/submissions")
async def list_submissions(
    form_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        result = await db.execute(
            select(LeadFormSubmission)
            .where(and_(LeadFormSubmission.form_id == form_id, LeadFormSubmission.org_id == org_id))
            .order_by(LeadFormSubmission.created_at.desc())
        )
        subs = result.scalars().all()
        return [_submission_out(s) for s in subs]
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_submissions failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/crm/lead-forms/{form_id}/submissions/{submission_id}/convert")
async def convert_submission(
    form_id: uuid.UUID,
    submission_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        result = await db.execute(
            select(LeadFormSubmission).where(
                and_(
                    LeadFormSubmission.id == submission_id,
                    LeadFormSubmission.form_id == form_id,
                    LeadFormSubmission.org_id == org_id,
                )
            )
        )
        sub = result.scalars().first()
        if not sub:
            raise HTTPException(status_code=404, detail="Submission not found")
        from app.models.crm import Deal
        from decimal import Decimal
        deal = Deal(
            id=uuid.uuid4(),
            org_id=org_id,
            title=sub.submitter_name or sub.submitter_email or "Lead from form",
            stage="prospect",
        )
        db.add(deal)
        sub.converted_to_deal_id = deal.id
        await db.commit()
        await db.refresh(deal)
        return {"deal_id": str(deal.id)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("convert_submission failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Public endpoint (no auth) ────────────────────────────────────────────────

class FormSubmitBody(BaseModel):
    data: dict[str, Any]


@router.get("/api/forms/{slug}")
async def get_form_public(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Return form metadata for public rendering (no sensitive org data)."""
    try:
        result = await db.execute(
            select(LeadForm).where(and_(LeadForm.slug == slug, LeadForm.is_active.is_(True)))
        )
        form = result.scalars().first()
        if not form:
            raise HTTPException(status_code=404, detail="Form not found")
        return {
            "title": form.title,
            "description": form.description,
            "fields": form.fields,
            "redirect_url": form.redirect_url,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_form_public failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/forms/{slug}/submit", status_code=201)
async def submit_form(
    slug: str,
    body: FormSubmitBody,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(LeadForm).where(and_(LeadForm.slug == slug, LeadForm.is_active.is_(True)))
        )
        form = result.scalars().first()
        if not form:
            raise HTTPException(status_code=404, detail="Form not found")

        # Validate required fields
        for field in form.fields:
            if field.get("required") and not body.data.get(field.get("name")):
                raise HTTPException(status_code=422, detail=f"Field '{field.get('label', field.get('name'))}' is required")

        # Extract email/name from typed fields
        submitter_email: Optional[str] = None
        submitter_name: Optional[str] = None
        for field in form.fields:
            field_name = field.get("name")
            if field.get("type") == "email" and field_name:
                submitter_email = body.data.get(field_name)
            if field_name in ("name", "full_name") and not submitter_name:
                submitter_name = body.data.get(field_name)

        sub = LeadFormSubmission(
            id=uuid.uuid4(),
            form_id=form.id,
            org_id=form.org_id,
            data=body.data,
            submitter_email=submitter_email,
            submitter_name=submitter_name,
        )
        db.add(sub)
        await db.commit()

        # Send notification email if configured
        if form.notify_email and submitter_email:
            try:
                from app.services.email import send_campaign_email
                await send_campaign_email(
                    to_email=form.notify_email,
                    subject=f"New lead form submission: {form.title}",
                    body_html=f"<p>New submission from <strong>{submitter_name or submitter_email}</strong></p>",
                    org_name="",
                )
            except Exception:
                log.warning("submit_form: notify email failed for form=%s", form.id)

        return {"success": True, "redirect_url": form.redirect_url}
    except HTTPException:
        raise
    except Exception as e:
        log.error("submit_form failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
