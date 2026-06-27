"""Role-based field masking configuration

Allows org admins to configure which fields are masked for MEMBER/VIEWER roles.

Endpoints:
  GET    /api/compliance/field-masking           list all rules
  POST   /api/compliance/field-masking           create or update a rule
  DELETE /api/compliance/field-masking/{id}      delete a rule
  POST   /api/compliance/field-masking/defaults  install default rules
  POST   /api/compliance/field-masking/preview   preview masking on sample data
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from .models import FieldMaskingRule
from app.services.field_masking import DEFAULT_MEMBER_RULES, mask_value

router = APIRouter(prefix="/api/compliance/field-masking", tags=["compliance_field_masking"], dependencies=[Depends(require_module("compliance"))])
log = logging.getLogger(__name__)

VALID_ROLES = {"member", "viewer", "accountant"}
VALID_RESOURCES = {"invoice", "customer", "supplier", "expense", "payroll"}
VALID_MASK_STYLES = {"obfuscate", "partial", "hidden"}


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


class RuleIn(BaseModel):
    role: str
    resource: str
    field: str
    mask_style: str = "obfuscate"
    enabled: bool = True

class RuleOut(BaseModel):
    id: str
    role: str
    resource: str
    field: str
    mask_style: str
    enabled: bool


def _out(r: FieldMaskingRule) -> RuleOut:
    return RuleOut(id=str(r.id), role=r.role, resource=r.resource,
                   field=r.field, mask_style=r.mask_style, enabled=r.enabled)


class PreviewIn(BaseModel):
    resource: str
    role: str
    sample: dict   # e.g. {"total_amount": "12345.00", "email": "john@acme.com"}


@router.get("")
async def list_rules(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        rows = await db.execute(
            select(FieldMaskingRule)
            .where(FieldMaskingRule.org_id == org_id)
            .order_by(FieldMaskingRule.role, FieldMaskingRule.resource, FieldMaskingRule.field)
        )
        return {"rules": [_out(r) for r in rows.scalars()]}
    except Exception as e:
        log.error("list_masking_rules failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=RuleOut)
async def upsert_rule(
    body: RuleIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        if body.role not in VALID_ROLES:
            raise HTTPException(status_code=422, detail=f"role must be one of {VALID_ROLES}")
        if body.resource not in VALID_RESOURCES:
            raise HTTPException(status_code=422, detail=f"resource must be one of {VALID_RESOURCES}")
        if body.mask_style not in VALID_MASK_STYLES:
            raise HTTPException(status_code=422, detail=f"mask_style must be one of {VALID_MASK_STYLES}")

        # Upsert: find existing or create
        row_q = await db.execute(
            select(FieldMaskingRule).where(
                FieldMaskingRule.org_id == org_id,
                FieldMaskingRule.role == body.role,
                FieldMaskingRule.resource == body.resource,
                FieldMaskingRule.field == body.field,
            )
        )
        rule = row_q.scalar_one_or_none()
        if rule:
            rule.mask_style = body.mask_style
            rule.enabled = body.enabled
        else:
            rule = FieldMaskingRule(
                org_id=org_id,
                role=body.role, resource=body.resource,
                field=body.field, mask_style=body.mask_style,
                enabled=body.enabled,
            )
            db.add(rule)
        await db.commit()
        await db.refresh(rule)
        return _out(rule)
    except HTTPException:
        raise
    except Exception as e:
        log.error("upsert_masking_rule failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(FieldMaskingRule).where(
                FieldMaskingRule.id == rule_id, FieldMaskingRule.org_id == org_id
            )
        )
        rule = row.scalar_one_or_none()
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        await db.delete(rule)
        await db.commit()
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_masking_rule failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/defaults")
async def install_defaults(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Install Varuflow's recommended masking rules for MEMBER and VIEWER.
    Safe to call multiple times — skips existing rules."""
    org_id = _org(ctx)
    try:
        created = 0
        for (role, resource, field, style) in DEFAULT_MEMBER_RULES:
            existing = await db.execute(
                select(FieldMaskingRule).where(
                    FieldMaskingRule.org_id == org_id,
                    FieldMaskingRule.role == role,
                    FieldMaskingRule.resource == resource,
                    FieldMaskingRule.field == field,
                )
            )
            if not existing.scalar_one_or_none():
                db.add(FieldMaskingRule(
                    org_id=org_id, role=role, resource=resource,
                    field=field, mask_style=style, enabled=True,
                ))
                created += 1
        await db.commit()
        return {"created": created, "message": f"Installed {created} default masking rules"}
    except Exception as e:
        log.error("install_defaults failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/preview")
async def preview_masking(
    body: PreviewIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Show before/after for a sample dict with current rules applied."""
    org_id = _org(ctx)
    try:
        from app.services.field_masking import apply_masks
        masked = await apply_masks(body.sample, body.resource, body.role, org_id, db)
        return {"original": body.sample, "masked": masked}
    except Exception as e:
        log.error("preview_masking failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
