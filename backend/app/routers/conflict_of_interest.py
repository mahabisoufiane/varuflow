"""Conflict of Interest Register — staff declarations and admin reviews.

Endpoints
─────────
GET    /api/conflicts           → list (managers see all, staff see own)
POST   /api/conflicts           → declare conflict (own user_id)
GET    /api/conflicts/{id}      → detail
PATCH  /api/conflicts/{id}      → update own pending / admin review
DELETE /api/conflicts/{id}      → admin or own pending
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.conflict_register import ConflictDeclaration
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/conflicts", tags=["conflict_of_interest"], dependencies=[Depends(require_module("hr"))])
log = logging.getLogger(__name__)

_ADMIN_ROLES = {"admin", "owner", "manager"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    user, _ = ctx
    return uuid.UUID(str(user["user_id"]))


def _is_admin(ctx: tuple) -> bool:
    _, member = ctx
    return getattr(member, "role", None) in _ADMIN_ROLES


def _declaration_out(d: ConflictDeclaration) -> dict[str, Any]:
    return {
        "id": str(d.id),
        "org_id": str(d.org_id),
        "user_id": str(d.user_id),
        "declaration_type": d.declaration_type,
        "counterparty_name": d.counterparty_name,
        "counterparty_type": d.counterparty_type,
        "relationship_description": d.relationship_description,
        "declared_value": float(d.declared_value) if d.declared_value is not None else None,
        "currency": d.currency,
        "is_reviewed": d.is_reviewed,
        "reviewed_by": str(d.reviewed_by) if d.reviewed_by else None,
        "reviewed_at": d.reviewed_at.isoformat() if d.reviewed_at else None,
        "review_notes": d.review_notes,
        "status": d.status,
        "created_at": d.created_at.isoformat(),
        "updated_at": d.updated_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class DeclarationIn(BaseModel):
    declaration_type: str
    counterparty_name: str = Field(min_length=1, max_length=300)
    counterparty_type: Optional[str] = None
    relationship_description: Optional[str] = None
    declared_value: Optional[float] = None
    currency: str = Field(default="SEK", max_length=3)


class DeclarationPatch(BaseModel):
    # Fields staff can update on own pending declaration
    counterparty_name: Optional[str] = Field(default=None, max_length=300)
    counterparty_type: Optional[str] = None
    relationship_description: Optional[str] = None
    declared_value: Optional[float] = None
    currency: Optional[str] = Field(default=None, max_length=3)
    # Admin-only review fields
    is_reviewed: Optional[bool] = None
    reviewed_by: Optional[uuid.UUID] = None
    review_notes: Optional[str] = None
    status: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_declarations(
    status: Optional[str] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    admin = _is_admin(ctx)
    try:
        q = select(ConflictDeclaration).where(ConflictDeclaration.org_id == org_id)
        if not admin:
            q = q.where(ConflictDeclaration.user_id == user_id)
        if status:
            q = q.where(ConflictDeclaration.status == status)
        q = q.order_by(ConflictDeclaration.created_at.desc())
        rows = (await db.execute(q)).scalars().all()
        return [_declaration_out(d) for d in rows]
    except Exception as e:
        log.error("list_declarations failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_declaration(
    body: DeclarationIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    try:
        decl = ConflictDeclaration(
            org_id=org_id,
            user_id=user_id,
            declaration_type=body.declaration_type,
            counterparty_name=body.counterparty_name,
            counterparty_type=body.counterparty_type,
            relationship_description=body.relationship_description,
            declared_value=body.declared_value,
            currency=body.currency,
            status="pending",
            is_reviewed=False,
        )
        db.add(decl)
        await db.commit()
        await db.refresh(decl)
        return _declaration_out(decl)
    except Exception as e:
        log.error("create_declaration failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{decl_id}")
async def get_declaration(
    decl_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        decl = await db.scalar(
            select(ConflictDeclaration).where(
                ConflictDeclaration.id == decl_id,
                ConflictDeclaration.org_id == org_id,
            )
        )
        if not decl:
            raise HTTPException(status_code=404, detail="Declaration not found")
        return _declaration_out(decl)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_declaration failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{decl_id}")
async def patch_declaration(
    decl_id: uuid.UUID,
    body: DeclarationPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    admin = _is_admin(ctx)
    try:
        decl = await db.scalar(
            select(ConflictDeclaration).where(
                ConflictDeclaration.id == decl_id,
                ConflictDeclaration.org_id == org_id,
            )
        )
        if not decl:
            raise HTTPException(status_code=404, detail="Declaration not found")

        # Staff can only update their own pending declarations
        if not admin:
            if decl.user_id != user_id:
                raise HTTPException(status_code=403, detail="Not authorised")
            if decl.status != "pending":
                raise HTTPException(status_code=403, detail="Can only edit pending declarations")

        # Common fields (staff or admin)
        for field in ("counterparty_name", "counterparty_type", "relationship_description", "declared_value", "currency"):
            val = getattr(body, field)
            if val is not None:
                setattr(decl, field, val)

        # Admin-only fields
        if admin:
            if body.is_reviewed is not None:
                decl.is_reviewed = body.is_reviewed
                if body.is_reviewed:
                    decl.reviewed_by = body.reviewed_by or user_id
                    decl.reviewed_at = datetime.now(timezone.utc)
            if body.review_notes is not None:
                decl.review_notes = body.review_notes
            if body.status is not None:
                decl.status = body.status

        decl.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(decl)
        return _declaration_out(decl)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_declaration failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{decl_id}", status_code=204)
async def delete_declaration(
    decl_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    admin = _is_admin(ctx)
    try:
        decl = await db.scalar(
            select(ConflictDeclaration).where(
                ConflictDeclaration.id == decl_id,
                ConflictDeclaration.org_id == org_id,
            )
        )
        if not decl:
            raise HTTPException(status_code=404, detail="Declaration not found")

        if not admin:
            if decl.user_id != user_id or decl.status != "pending":
                raise HTTPException(status_code=403, detail="Not authorised")

        await db.delete(decl)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_declaration failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
