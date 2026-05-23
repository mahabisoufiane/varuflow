"""Audit log read endpoint — owners can inspect sensitive actions.

Write paths are scattered across gdpr, billing, team. This router gives
owners a single place to review what happened. Read-only by design;
rows are never updated or deleted through the API.

Endpoint:
  GET /api/audit?action=&limit=&offset=

Restricted to OWNER role. Always scoped to caller's org_id.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.audit import AuditLogEntry
from app.models.organization import OrgRole

router = APIRouter(prefix="/api/audit", tags=["audit"])

log = logging.getLogger(__name__)


class AuditEntryOut(BaseModel):
    id:           str
    action:       str
    target_type:  str | None
    target_id:    str | None
    actor_user_id: str | None
    ip_address:   str | None
    extra:        dict[str, Any] | None
    created_at:   datetime


@router.get("", response_model=list[AuditEntryOut])
async def list_audit_entries(
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
    action: str | None = Query(default=None, max_length=64),
    limit:  int  = Query(default=50,  ge=1, le=200),
    offset: int  = Query(default=0,   ge=0),
):
    try:
        _, member = ctx
        if member.role != OrgRole.OWNER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")

        stmt = (
            select(AuditLogEntry)
            .where(AuditLogEntry.org_id == member.org_id)
            .order_by(AuditLogEntry.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if action:
            stmt = stmt.where(AuditLogEntry.action == action)

        rows = (await db.scalars(stmt)).all()
        return [
            AuditEntryOut(
                id=str(r.id),
                action=r.action,
                target_type=r.target_type,
                target_id=r.target_id,
                actor_user_id=str(r.actor_user_id) if r.actor_user_id else None,
                ip_address=r.ip_address,
                extra=r.extra or {},
                created_at=r.created_at,
            )
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        log.error("audit_list failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
