"""Customer API Keys — Sprint 14

Endpoints:
  GET    /api/customer-api-keys       list keys for org (no key_hash)
  POST   /api/customer-api-keys       create key; returns plaintext ONCE
  GET    /api/customer-api-keys/{id}  detail (no key_hash)
  PATCH  /api/customer-api-keys/{id}  update name/scopes/is_active/expires_at
  DELETE /api/customer-api-keys/{id}  revoke
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime
from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.customer_api_key import CustomerApiKey
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/customer-api-keys", tags=["integrations_api_keys"], dependencies=[Depends(require_module("settings"))])
log = logging.getLogger(__name__)

KEY_PREFIX_STR = "vf_"
KEY_LENGTH = 40  # total random chars after prefix


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _generate_key() -> tuple[str, str, str]:
    """Returns (plaintext_key, key_hash, key_prefix)."""
    raw = secrets.token_urlsafe(KEY_LENGTH)
    plaintext = f"{KEY_PREFIX_STR}{raw}"
    key_prefix = plaintext[:12]
    hashed = bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt()).decode()
    return plaintext, hashed, key_prefix


def _to_dict(k: CustomerApiKey) -> dict:
    return {
        "id": str(k.id),
        "org_id": str(k.org_id),
        "customer_id": str(k.customer_id) if k.customer_id else None,
        "key_prefix": k.key_prefix,
        "name": k.name,
        "scopes": k.scopes,
        "is_active": k.is_active,
        "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        "expires_at": k.expires_at.isoformat() if k.expires_at else None,
        "created_at": k.created_at.isoformat() if k.created_at else None,
        "updated_at": k.updated_at.isoformat() if k.updated_at else None,
    }


class ApiKeyIn(BaseModel):
    customer_id: Optional[uuid.UUID] = None
    name: str
    scopes: list[str] = []
    expires_at: Optional[datetime] = None


class ApiKeyPatch(BaseModel):
    name: Optional[str] = None
    scopes: Optional[list[str]] = None
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None


@router.get("")
async def list_api_keys(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
):
    org_id = _org(ctx)
    try:
        result = await db.execute(
            select(CustomerApiKey)
            .where(CustomerApiKey.org_id == org_id)
            .offset(skip)
            .limit(limit)
        )
        keys = result.scalars().all()
        return {"items": [_to_dict(k) for k in keys], "total": len(keys)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_customer_api_keys failed: %s", str(e), extra={"org_id": str(org_id)})  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_api_key(
    body: ApiKeyIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        plaintext, key_hash, key_prefix = _generate_key()
        api_key = CustomerApiKey(
            org_id=org_id,
            customer_id=body.customer_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=body.name,
            scopes=body.scopes,
            expires_at=body.expires_at,
        )
        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)
        result = _to_dict(api_key)
        result["key"] = plaintext  # Returned only once
        return result
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_customer_api_key failed: %s", str(e), extra={"org_id": str(org_id)})  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{key_id}")
async def get_api_key(
    key_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        result = await db.execute(
            select(CustomerApiKey).where(
                CustomerApiKey.id == key_id,
                CustomerApiKey.org_id == org_id,
            )
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")
        return _to_dict(api_key)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_customer_api_key failed: %s", str(e), extra={"org_id": str(org_id)})  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{key_id}")
async def update_api_key(
    key_id: uuid.UUID,
    body: ApiKeyPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        result = await db.execute(
            select(CustomerApiKey).where(
                CustomerApiKey.id == key_id,
                CustomerApiKey.org_id == org_id,
            )
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")

        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(api_key, field, value)

        await db.commit()
        await db.refresh(api_key)
        return _to_dict(api_key)
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_customer_api_key failed: %s", str(e), extra={"org_id": str(org_id)})  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        result = await db.execute(
            select(CustomerApiKey).where(
                CustomerApiKey.id == key_id,
                CustomerApiKey.org_id == org_id,
            )
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")
        api_key.is_active = False
        await db.commit()
        return {"revoked": True, "id": str(key_id)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("revoke_customer_api_key failed: %s", str(e), extra={"org_id": str(org_id)})  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
        raise HTTPException(status_code=500, detail="Internal server error")
