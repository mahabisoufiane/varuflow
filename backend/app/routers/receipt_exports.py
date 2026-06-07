"""Receipt / invoice export log — Sprint 10.

Endpoints under ``/api/receipt-exports``:

    GET    ""       list exports (filter by customer_id, export_target)
    POST   ""       log an export; for CSV target returns a redirect-ready URL
    DELETE /{id}    remove log entry
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.receipt_export import ReceiptExport
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/receipt-exports", tags=["receipt-exports"], dependencies=[Depends(require_module("invoicing"))])
logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────────────

class ExportCreate(BaseModel):
    customer_id: uuid.UUID
    invoice_id: uuid.UUID | None = None
    export_target: str  # e.g. "csv", "fortnox", "email"
    export_ref: str | None = None


class ExportOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    invoice_id: uuid.UUID | None
    export_target: str
    exported_at: datetime
    export_ref: str | None
    created_at: datetime
    download_url: str | None = None


def _to_out(row: ReceiptExport, download_url: str | None = None) -> ExportOut:
    return ExportOut(
        id=row.id,
        org_id=row.org_id,
        customer_id=row.customer_id,
        invoice_id=row.invoice_id,
        export_target=row.export_target,
        exported_at=row.exported_at,
        export_ref=row.export_ref,
        created_at=row.created_at,
        download_url=download_url,
    )


async def _load(db: AsyncSession, *, export_id: uuid.UUID, org_id: uuid.UUID) -> ReceiptExport:
    row = await db.get(ReceiptExport, export_id)
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Export record not found")
    return row


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ExportOut])
async def list_exports(
    customer_id: uuid.UUID | None = Query(default=None),
    export_target: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        stmt = select(ReceiptExport).where(ReceiptExport.org_id == member.org_id)
        if customer_id is not None:
            stmt = stmt.where(ReceiptExport.customer_id == customer_id)
        if export_target is not None:
            stmt = stmt.where(ReceiptExport.export_target == export_target)
        stmt = stmt.order_by(ReceiptExport.exported_at.desc()).limit(limit).offset(offset)
        rows = (await db.scalars(stmt)).all()
        return [_to_out(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_exports failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=ExportOut, status_code=status.HTTP_201_CREATED)
async def log_export(
    body: ExportCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        row = ReceiptExport(
            org_id=member.org_id,
            customer_id=body.customer_id,
            invoice_id=body.invoice_id,
            export_target=body.export_target,
            export_ref=body.export_ref,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        download_url = None
        if body.export_target == "csv":
            download_url = f"/api/receipt-exports/{row.id}/download.csv"
        return _to_out(row, download_url=download_url)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"log_export failed: {str(e)}", extra={"org_id": str(member.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{export_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_export(
    export_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        row = await _load(db, export_id=export_id, org_id=member.org_id)
        await db.delete(row)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_export failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
