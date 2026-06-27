"""Accountant invoice forwarding config — Sprint 10.

Endpoints under ``/api/accountant-forwarding``:

    GET    /{customer_id}    get forwarding config
    PUT    /{customer_id}    upsert (set accountant_email, is_active)
    DELETE /{customer_id}    deactivate (is_active=false)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.accountant_forwarding import AccountantForwarding

router = APIRouter(prefix="/api/accountant-forwarding", tags=["accountant-forwarding"])
logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────────────

class ForwardingUpsert(BaseModel):
    accountant_email: EmailStr
    is_active: bool = True


class ForwardingOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    accountant_email: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


def _to_out(row: AccountantForwarding) -> ForwardingOut:
    return ForwardingOut(
        id=row.id,
        org_id=row.org_id,
        customer_id=row.customer_id,
        accountant_email=row.accountant_email,
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{customer_id}", response_model=ForwardingOut | None)
async def get_forwarding(
    customer_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        stmt = select(AccountantForwarding).where(
            AccountantForwarding.org_id == member.org_id,
            AccountantForwarding.customer_id == customer_id,
        )
        row = (await db.scalars(stmt)).first()
        return _to_out(row) if row else None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_forwarding failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{customer_id}", response_model=ForwardingOut)
async def upsert_forwarding(
    customer_id: uuid.UUID,
    body: ForwardingUpsert,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        stmt = select(AccountantForwarding).where(
            AccountantForwarding.org_id == member.org_id,
            AccountantForwarding.customer_id == customer_id,
        )
        row = (await db.scalars(stmt)).first()
        if row is None:
            row = AccountantForwarding(org_id=member.org_id, customer_id=customer_id)
            db.add(row)
        row.accountant_email = str(body.accountant_email)
        row.is_active = body.is_active
        await db.commit()
        await db.refresh(row)
        return _to_out(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"upsert_forwarding failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_forwarding(
    customer_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        stmt = select(AccountantForwarding).where(
            AccountantForwarding.org_id == member.org_id,
            AccountantForwarding.customer_id == customer_id,
        )
        row = (await db.scalars(stmt)).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Forwarding config not found")
        row.is_active = False
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"deactivate_forwarding failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
