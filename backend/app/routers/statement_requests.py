"""Statement requests router — Sprint 13.  prefix /api/statements"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.statement_request import StatementRequest
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/statements", tags=["statement-requests"], dependencies=[Depends(require_module("invoicing"))])


def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Schemas ────────────────────────────────────────────────────────────────────

class StatementRequestIn(BaseModel):
    customer_id: uuid.UUID
    requested_by: str = "customer"
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    format: str = "pdf"


class StatementRequestOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    requested_by: str
    date_from: Optional[str]
    date_to: Optional[str]
    format: str
    status: str
    file_url: Optional[str]
    generated_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[StatementRequestOut])
async def list_statements(
    customer_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        q = select(StatementRequest).where(StatementRequest.org_id == org_id)
        if customer_id:
            q = q.where(StatementRequest.customer_id == customer_id)
        if status:
            q = q.where(StatementRequest.status == status)
        q = q.order_by(StatementRequest.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(q)
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_statements failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=StatementRequestOut, status_code=201)
async def create_statement_request(
    body: StatementRequestIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        now = datetime.now(timezone.utc)
        # In production this would trigger async PDF generation.
        # For now set status=ready with a placeholder file_url.
        placeholder_url = (
            f"https://varuflow.vercel.app/statements/{uuid.uuid4()}.pdf"
        )
        req = StatementRequest(
            org_id=org_id,
            customer_id=body.customer_id,
            requested_by=body.requested_by,
            date_from=body.date_from,
            date_to=body.date_to,
            format=body.format,
            status="ready",
            file_url=placeholder_url,
            generated_at=now,
            expires_at=now + timedelta(days=7),
        )
        db.add(req)
        await db.commit()
        await db.refresh(req)
        return req
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_statement_request failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{statement_id}", response_model=StatementRequestOut)
async def get_statement(
    statement_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        req = await db.get(StatementRequest, statement_id)
        if not req or req.org_id != org_id:
            raise HTTPException(status_code=404, detail="Statement request not found")
        return req
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_statement failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{statement_id}", status_code=204)
async def delete_statement(
    statement_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        req = await db.get(StatementRequest, statement_id)
        if not req or req.org_id != org_id:
            raise HTTPException(status_code=404, detail="Statement request not found")
        await db.delete(req)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_statement failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
