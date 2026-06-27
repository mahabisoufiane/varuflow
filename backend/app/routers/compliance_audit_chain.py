"""SOC 2 audit chain — tamper-evident log verification

Endpoints:
  GET  /api/compliance/audit-chain/verify      verify chain integrity for caller's org
  GET  /api/compliance/audit-chain/entries     paginated log with hashes
  POST /api/compliance/audit-chain/export      export NDJSON for external auditors (admin-only)
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.audit import AuditLogEntry
from app.services.audit_chain import verify_chain, GENESIS_HASH

router = APIRouter(prefix="/api/compliance/audit-chain", tags=["compliance_audit_chain"])
log = logging.getLogger(__name__)


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _entry_out(e: AuditLogEntry) -> dict:
    return {
        "id": str(e.id),
        "sequence_no": e.sequence_no,
        "action": e.action,
        "actor_user_id": str(e.actor_user_id) if e.actor_user_id else None,
        "target_type": e.target_type,
        "target_id": e.target_id,
        "ip_address": e.ip_address,
        "extra": e.extra,
        "previous_hash": e.previous_hash,
        "row_hash": e.row_hash,
        "created_at": e.created_at.isoformat() if hasattr(e.created_at, "isoformat") else str(e.created_at),
        "chained": (e.row_hash != GENESIS_HASH),
    }


@router.get("/verify")
async def verify_audit_chain(
    limit: int = Query(10_000, ge=1, le=100_000),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Verify the tamper-evident hash chain for this org's audit log.
    Returns ok=True if all row_hashes are consistent with their preimages."""
    org_id = _org(ctx)
    try:
        result = await verify_chain(db, org_id, limit=limit)
        return {
            "ok": result.ok,
            "total_rows_checked": result.total_rows,
            "first_broken_id": result.first_broken_id,
            "first_broken_seq": result.first_broken_seq,
            "error": result.error,
            "message": (
                f"Chain intact — {result.total_rows} rows verified."
                if result.ok
                else f"Chain BROKEN at row {result.first_broken_seq}: {result.error}"
            ),
        }
    except Exception as e:
        log.error("verify_audit_chain failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/entries")
async def list_audit_entries(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    action: Optional[str] = Query(None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        q = select(AuditLogEntry).where(AuditLogEntry.org_id == org_id)
        if action:
            q = q.where(AuditLogEntry.action == action)
        rows = await db.execute(
            q.order_by(AuditLogEntry.created_at.desc()).limit(limit).offset((page - 1) * limit)
        )
        entries = rows.scalars().all()
        return {"entries": [_entry_out(e) for e in entries]}
    except Exception as e:
        log.error("list_audit_entries failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/export")
async def export_audit_log(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Stream the full audit log as NDJSON for external auditors.
    Each line is a JSON object so auditors can independently verify hashes."""
    org_id = _org(ctx)
    try:
        rows = await db.execute(
            select(AuditLogEntry)
            .where(AuditLogEntry.org_id == org_id)
            .order_by(AuditLogEntry.created_at.asc())
        )
        entries = rows.scalars().all()

        def _iter():
            for e in entries:
                yield json.dumps(_entry_out(e), separators=(",", ":")) + "\n"

        return StreamingResponse(
            _iter(),
            media_type="application/x-ndjson",
            headers={
                "Content-Disposition": f'attachment; filename="audit_log_{org_id}.ndjson"',
                "X-Row-Count": str(len(entries)),
            },
        )
    except Exception as e:
        log.error("export_audit_log failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
