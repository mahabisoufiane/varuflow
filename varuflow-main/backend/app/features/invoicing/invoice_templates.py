"""Custom invoice template router (Item 42).

Endpoints under ``/api/invoice-templates``:

* ``GET    /``                     — list templates for the org.
* ``POST   /``                     — create a template.
* ``GET    /{id}``                 — fetch a single template.
* ``PATCH  /{id}``                 — update a template.
* ``DELETE /{id}``                 — soft-delete (``is_active=False``).
* ``POST   /{id}/set-default``     — promote to default.
* ``POST   /{id}/preview``         — live HTML preview.

All mutations audit via :func:`log_action`.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.features.invoicing.model_invoice_templates import InvoiceTemplate
from app.services import template_renderer as tpl
from app.services.audit import log_action
from app.middleware.plan_check import require_module

router = APIRouter(
    prefix="/api/invoice-templates",
    tags=["invoicing", "templates"],
    dependencies=[Depends(require_module("invoicing"))],
)


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _actor(ctx: tuple) -> uuid.UUID | None:
    user, _ = ctx
    uid = user.get("user_id")
    if isinstance(uid, uuid.UUID):
        return uid
    try:
        return uuid.UUID(str(uid))
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════


class TemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    logo_url: str | None = Field(default=None, max_length=1024)
    primary_color: str = Field(default="#1a2332")
    accent_color: str = Field(default="#2563eb")
    font_family: str = Field(default="Helvetica")
    show_bank_details: bool = True
    show_qr_code: bool = False
    footer_text: str | None = None
    header_text: str | None = None

    @field_validator("primary_color", "accent_color")
    @classmethod
    def _check_hex(cls, v: str) -> str:
        try:
            return tpl.validate_hex_color(v)
        except ValueError:
            raise ValueError("color must be a #RRGGBB hex string")


class TemplateCreateIn(TemplateBase):
    is_default: bool = False


class TemplateUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    logo_url: str | None = None
    primary_color: str | None = None
    accent_color: str | None = None
    font_family: str | None = None
    show_bank_details: bool | None = None
    show_qr_code: bool | None = None
    footer_text: str | None = None
    header_text: str | None = None

    @field_validator("primary_color", "accent_color")
    @classmethod
    def _check_hex(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            return tpl.validate_hex_color(v)
        except ValueError:
            raise ValueError("color must be a #RRGGBB hex string")


class TemplateOut(BaseModel):
    id: uuid.UUID | None
    name: str
    is_default: bool
    logo_url: str | None
    primary_color: str
    accent_color: str
    font_family: str
    show_bank_details: bool
    show_qr_code: bool
    footer_text: str | None
    header_text: str | None
    is_active: bool


class PreviewIn(BaseModel):
    org_name: str = Field(default="Example AB", max_length=200)
    invoice_number: str = Field(default="INV-000123", max_length=60)


class PreviewOut(BaseModel):
    html: str


# ═══════════════════════════════════════════════════════════════════
# Loaders
# ═══════════════════════════════════════════════════════════════════


async def _load(
    db: AsyncSession, *, template_id: uuid.UUID, org_id: uuid.UUID,
) -> InvoiceTemplate:
    row = await db.scalar(
        select(InvoiceTemplate).where(
            InvoiceTemplate.id == template_id,
            InvoiceTemplate.org_id == org_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="template_not_found")
    return row


# ═══════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════


@router.get("", response_model=list[TemplateOut])
async def list_templates(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    rows = (
        await db.execute(
            select(InvoiceTemplate)
            .where(InvoiceTemplate.org_id == org_id)
            .order_by(InvoiceTemplate.is_default.desc(), InvoiceTemplate.name.asc())
        )
    ).scalars().all()
    return [TemplateOut(**tpl.template_to_dict(r)) for r in rows]


@router.get("/{template_id}", response_model=TemplateOut)
async def get_template(
    template_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    row = await _load(db, template_id=template_id, org_id=_org(ctx))
    return TemplateOut(**tpl.template_to_dict(row))


@router.post("", response_model=TemplateOut, status_code=201)
async def create_template(
    body: TemplateCreateIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)

    row = InvoiceTemplate(
        id=uuid.uuid4(),
        org_id=org_id,
        name=body.name.strip(),
        is_default=bool(body.is_default),
        logo_url=body.logo_url,
        primary_color=body.primary_color,
        accent_color=body.accent_color,
        font_family=tpl.normalise_font_family(body.font_family),
        show_bank_details=body.show_bank_details,
        show_qr_code=body.show_qr_code,
        footer_text=body.footer_text,
        header_text=body.header_text,
        is_active=True,
    )
    if body.is_default:
        # Clear before insert — avoid tripping the partial unique index.
        await tpl.clear_default(db, org_id=org_id)
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="invoice_template.created",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="invoice_template",
        target_id=str(row.id),
        request=request,
        extra={"name": row.name, "is_default": row.is_default},
    )
    await db.commit()
    await db.refresh(row)
    return TemplateOut(**tpl.template_to_dict(row))


@router.patch("/{template_id}", response_model=TemplateOut)
async def update_template(
    template_id: uuid.UUID,
    body: TemplateUpdateIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    row = await _load(db, template_id=template_id, org_id=org_id)

    payload = body.model_dump(exclude_unset=True)
    changes: dict[str, Any] = {}
    for field in (
        "name", "logo_url", "primary_color", "accent_color",
        "font_family", "show_bank_details", "show_qr_code",
        "footer_text", "header_text",
    ):
        if field in payload:
            value = payload[field]
            if field == "font_family":
                value = tpl.normalise_font_family(value)
            if field == "name" and isinstance(value, str):
                value = value.strip()
            setattr(row, field, value)
            changes[field] = value

    await db.flush()
    await log_action(
        db,
        action="invoice_template.updated",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="invoice_template",
        target_id=str(row.id),
        request=request,
        extra={"fields": list(changes.keys())},
    )
    await db.commit()
    await db.refresh(row)
    return TemplateOut(**tpl.template_to_dict(row))


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete by flipping ``is_active`` to false. Keeps
    historical references (future ``invoice.template_id``) intact.
    """
    org_id = _org(ctx)
    row = await _load(db, template_id=template_id, org_id=org_id)
    row.is_active = False
    # A retired template cannot also be the default.
    was_default = row.is_default
    row.is_default = False
    await db.flush()
    await log_action(
        db,
        action="invoice_template.deleted",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="invoice_template",
        target_id=str(row.id),
        request=request,
        extra={"was_default": was_default},
    )
    await db.commit()


@router.post("/{template_id}/set-default", response_model=TemplateOut)
async def set_default(
    template_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    row = await _load(db, template_id=template_id, org_id=org_id)
    if not row.is_active:
        raise HTTPException(status_code=400, detail="template_inactive")

    await tpl.clear_default(db, org_id=org_id, except_id=row.id)
    row.is_default = True
    await db.flush()
    await log_action(
        db,
        action="invoice_template.set_default",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="invoice_template",
        target_id=str(row.id),
        request=request,
        extra={"name": row.name},
    )
    await db.commit()
    await db.refresh(row)
    return TemplateOut(**tpl.template_to_dict(row))


@router.post("/{template_id}/preview", response_model=PreviewOut)
async def preview_template(
    template_id: uuid.UUID,
    body: PreviewIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    row = await _load(db, template_id=template_id, org_id=org_id)
    html = tpl.build_preview_html(
        tpl.template_to_dict(row),
        org_name=body.org_name,
        invoice_number=body.invoice_number,
    )
    return PreviewOut(html=html)
