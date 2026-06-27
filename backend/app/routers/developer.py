"""API developer keys router (Item 45) — ENTERPRISE-only.

Endpoints under ``/api/developer/keys``:

* ``GET    /``                 — list keys (no plaintext, ever)
* ``POST   /``                 — issue a new key (plaintext shown ONCE)
* ``POST   /{id}/rotate``      — issue replacement, revoke the old one
* ``POST   /{id}/revoke``      — revoke immediately
* ``GET    /{id}/usage``       — last 100 calls

All mutations audit via :func:`log_action`. Plan gate: ENTERPRISE.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_plan
from app.models.developer import ApiKey, ApiKeyUsage
from app.models.organization import OrgPlan, OrgRole
from app.services import developer_key_service as svc
from app.services.audit import log_action


router = APIRouter(
    prefix="/api/developer/keys",
    tags=["developer"],
    dependencies=[Depends(require_plan(OrgPlan.ENTERPRISE))],
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


def _require_owner_or_admin(ctx: tuple) -> None:
    """API keys grant programmatic access to tenant data; only owners
    and admins can create or revoke them."""
    _, member = ctx
    if member.role not in (OrgRole.OWNER, OrgRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can manage API keys",
        )


# ═══════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════


class ApiKeyCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    scopes: list[str] = Field(..., min_length=1)
    expires_at: datetime | None = None

    @field_validator("scopes")
    @classmethod
    def _scopes(cls, v):
        try:
            return svc.validate_scopes(v)
        except svc.ApiKeyValidationError as exc:
            raise ValueError(str(exc))


class ApiKeyOut(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    scopes: list[str]
    last_used_at: datetime | None
    expires_at: datetime | None
    is_revoked: bool
    created_at: datetime
    created_by: uuid.UUID | None

    @classmethod
    def from_row(cls, row: ApiKey) -> "ApiKeyOut":
        return cls(
            id=row.id,
            name=row.name,
            key_prefix=row.key_prefix,
            scopes=list(row.scopes or []),
            last_used_at=row.last_used_at,
            expires_at=row.expires_at,
            is_revoked=row.is_revoked,
            created_at=row.created_at,
            created_by=row.created_by,
        )


class ApiKeyIssuedOut(ApiKeyOut):
    """Returned ONLY at create / rotate time. The ``plaintext`` field
    is the one and only chance the operator gets to see the secret."""
    plaintext: str = Field(..., description="Shown once. Cannot be recovered.")


class ApiKeyUsageOut(BaseModel):
    id: uuid.UUID
    called_at: datetime
    method: str
    path: str
    status_code: int | None
    ip: str | None


# ═══════════════════════════════════════════════════════════════════
# Loader
# ═══════════════════════════════════════════════════════════════════


async def _load(
    db: AsyncSession, *, key_id: uuid.UUID, org_id: uuid.UUID,
) -> ApiKey:
    row = await db.scalar(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.org_id == org_id)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="api_key_not_found")
    return row


# ═══════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════


@router.get("", response_model=list[ApiKeyOut])
async def list_keys(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    rows = (
        await db.execute(
            select(ApiKey)
            .where(ApiKey.org_id == org_id)
            .order_by(ApiKey.created_at.desc())
        )
    ).scalars().all()
    return [ApiKeyOut.from_row(r) for r in rows]


@router.post("", response_model=ApiKeyIssuedOut, status_code=201)
async def create_key(
    body: ApiKeyCreateIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _require_owner_or_admin(ctx)
    org_id = _org(ctx)

    name = svc.validate_name(body.name)
    scopes = svc.validate_scopes(body.scopes)
    generated = svc.generate_key()

    row = ApiKey(
        id=uuid.uuid4(),
        org_id=org_id,
        name=name,
        key_prefix=generated.prefix,
        key_hash=generated.hash,
        scopes=scopes,
        expires_at=body.expires_at,
        created_by=_actor(ctx),
        is_revoked=False,
    )
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="api_key.created",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="api_key",
        target_id=str(row.id),
        request=request,
        extra={"name": name, "scopes": scopes, "prefix": generated.prefix},
    )
    await db.commit()
    await db.refresh(row)

    out = ApiKeyIssuedOut.from_row(row).model_copy(
        update={"plaintext": generated.plaintext}
    )
    return out


@router.post("/{key_id}/rotate", response_model=ApiKeyIssuedOut)
async def rotate_key(
    key_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Issue a replacement key with the same name + scopes; revoke
    the original atomically. Operators rotate on suspected leak or
    on a regular cadence."""
    _require_owner_or_admin(ctx)
    org_id = _org(ctx)

    old = await _load(db, key_id=key_id, org_id=org_id)
    if old.is_revoked:
        raise HTTPException(status_code=409, detail="already_revoked")

    generated = svc.generate_key()
    new = ApiKey(
        id=uuid.uuid4(),
        org_id=org_id,
        name=old.name,
        key_prefix=generated.prefix,
        key_hash=generated.hash,
        scopes=list(old.scopes or []),
        expires_at=old.expires_at,
        created_by=_actor(ctx),
        is_revoked=False,
    )
    old.is_revoked = True
    db.add(new)
    await db.flush()
    await log_action(
        db,
        action="api_key.rotated",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="api_key",
        target_id=str(new.id),
        request=request,
        extra={"old_id": str(old.id), "old_prefix": old.key_prefix,
               "new_prefix": generated.prefix},
    )
    await db.commit()
    await db.refresh(new)

    return ApiKeyIssuedOut.from_row(new).model_copy(
        update={"plaintext": generated.plaintext}
    )


@router.post("/{key_id}/revoke", status_code=204)
async def revoke_key(
    key_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _require_owner_or_admin(ctx)
    org_id = _org(ctx)
    row = await _load(db, key_id=key_id, org_id=org_id)
    if row.is_revoked:
        return
    row.is_revoked = True
    await db.flush()
    await log_action(
        db,
        action="api_key.revoked",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="api_key",
        target_id=str(row.id),
        request=request,
        extra={"name": row.name, "prefix": row.key_prefix},
    )
    await db.commit()


@router.get("/{key_id}/usage", response_model=list[ApiKeyUsageOut])
async def list_usage(
    key_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Last :data:`svc.USAGE_LOG_LIMIT` calls for a key, newest first."""
    org_id = _org(ctx)
    # Existence-and-tenant check.
    await _load(db, key_id=key_id, org_id=org_id)
    rows = (
        await db.execute(
            select(ApiKeyUsage)
            .where(ApiKeyUsage.key_id == key_id)
            .order_by(ApiKeyUsage.called_at.desc())
            .limit(svc.USAGE_LOG_LIMIT)
        )
    ).scalars().all()
    return [
        ApiKeyUsageOut(
            id=r.id,
            called_at=r.called_at,
            method=r.method,
            path=r.path,
            status_code=r.status_code,
            ip=r.ip,
        )
        for r in rows
    ]
