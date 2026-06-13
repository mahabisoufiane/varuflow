"""Document storage router (Item 44).

Endpoints under ``/api/documents``:

* ``GET    /``                     — list with filter + tag search.
* ``POST   /``                     — create (register uploaded URL).
* ``GET    /{id}``                 — fetch detail (respects is_shared).
* ``PATCH  /{id}``                 — update metadata / tags / link / share.
* ``DELETE /{id}``                 — delete (GDPR-safe hard delete).
* ``GET    /expiring``             — upcoming expirations + expired.
* ``GET    /linked/{type}/{id}``   — docs attached to a supplier / customer / product.

All mutations audit via :func:`log_action`.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.documents import Document
from app.models.organization import OrgRole
from app.services import document_service as svc
from app.services.audit import log_action


router = APIRouter(prefix="/api/documents", tags=["documents"])


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _member(ctx: tuple):
    _, member = ctx
    return member


def _actor(ctx: tuple) -> uuid.UUID | None:
    user, _ = ctx
    uid = user.get("user_id")
    if isinstance(uid, uuid.UUID):
        return uid
    try:
        return uuid.UUID(str(uid))
    except Exception:
        return None


def _can_view(row: Document, ctx: tuple) -> bool:
    """Access rule: shared docs are visible to everyone in the org;
    private docs to the uploader and owners/admins."""
    if row.is_shared:
        return True
    m = _member(ctx)
    if m.role in (OrgRole.OWNER, OrgRole.ADMIN):
        return True
    return row.uploaded_by == _actor(ctx)


# ═══════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════


class DocumentCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    category: str = Field(default="other")
    file_url: str = Field(..., min_length=1, max_length=2048)
    file_size: int = Field(..., gt=0)
    mime_type: str = Field(..., max_length=120)
    tags: list[str] = Field(default_factory=list)
    linked_type: str | None = None
    linked_id: uuid.UUID | None = None
    expires_at: datetime | None = None
    is_shared: bool = True
    description: str | None = None

    @field_validator("mime_type")
    @classmethod
    def _mime(cls, v):
        try:
            return svc.validate_mime(v)
        except svc.DocumentValidationError as exc:
            raise ValueError(str(exc))

    @field_validator("file_size")
    @classmethod
    def _size(cls, v):
        try:
            return svc.validate_size(v)
        except svc.DocumentValidationError as exc:
            raise ValueError(str(exc))

    @field_validator("linked_type")
    @classmethod
    def _link(cls, v):
        try:
            return svc.validate_linked_type(v)
        except svc.DocumentValidationError as exc:
            raise ValueError(str(exc))


class DocumentUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    category: str | None = None
    tags: list[str] | None = None
    linked_type: str | None = None
    linked_id: uuid.UUID | None = None
    expires_at: datetime | None = None
    is_shared: bool | None = None
    description: str | None = None

    @field_validator("linked_type")
    @classmethod
    def _link(cls, v):
        if v is None:
            return v
        try:
            return svc.validate_linked_type(v)
        except svc.DocumentValidationError as exc:
            raise ValueError(str(exc))


class DocumentOut(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    file_url: str
    file_size: int
    mime_type: str
    tags: list[str]
    uploaded_by: uuid.UUID | None
    linked_type: str | None
    linked_id: uuid.UUID | None
    expires_at: datetime | None
    is_shared: bool
    description: str | None
    created_at: datetime
    expiry_alert: bool
    days_until_expiry: int | None

    @classmethod
    def from_row(cls, row: Document) -> "DocumentOut":
        st = svc.expiry_status(row.expires_at)
        return cls(
            id=row.id,
            name=row.name,
            category=row.category,
            file_url=row.file_url,
            file_size=row.file_size,
            mime_type=row.mime_type,
            tags=list(row.tags or []),
            uploaded_by=row.uploaded_by,
            linked_type=row.linked_type,
            linked_id=row.linked_id,
            expires_at=row.expires_at,
            is_shared=row.is_shared,
            description=row.description,
            created_at=row.created_at,
            expiry_alert=st.alert,
            days_until_expiry=st.days_until,
        )


# ═══════════════════════════════════════════════════════════════════
# Loader
# ═══════════════════════════════════════════════════════════════════


async def _load(
    db: AsyncSession, *, doc_id: uuid.UUID, org_id: uuid.UUID,
) -> Document:
    row = await db.scalar(
        select(Document).where(
            Document.id == doc_id, Document.org_id == org_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="document_not_found")
    return row


# ═══════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════


@router.get("")
async def list_documents(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    category: str | None = Query(default=None),
    tag: list[str] | None = Query(default=None),
    q: str | None = Query(default=None, description="name/description search"),
    linked_type: str | None = Query(default=None),
    linked_id: uuid.UUID | None = Query(default=None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    org_id = _org(ctx)
    base = select(Document).where(Document.org_id == org_id)

    # Private documents are visible to owners/admins and their uploader.
    m = _member(ctx)
    if m.role == OrgRole.MEMBER:
        actor = _actor(ctx)
        base = base.where(
            or_(
                Document.is_shared == True,  # noqa: E712
                Document.uploaded_by == actor,
            )
        )

    if category:
        base = base.where(Document.category == svc.validate_category(category))
    if tag:
        tags = svc.normalise_tags(tag)
        if tags:
            base = base.where(Document.tags.contains(tags))
    if q:
        like = f"%{q.strip()}%"
        base = base.where(
            or_(
                Document.name.ilike(like),
                Document.description.ilike(like),
            )
        )
    if linked_type:
        base = base.where(
            Document.linked_type == svc.validate_linked_type(linked_type)
        )
    if linked_id is not None:
        base = base.where(Document.linked_id == linked_id)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    total_pages = (total + limit - 1) // limit if total > 0 else 0

    query = base.order_by(Document.created_at.desc()).offset((page - 1) * limit).limit(limit)
    rows = (await db.execute(query)).scalars().all()
    return {
        "items": [DocumentOut.from_row(r) for r in rows],
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


@router.get("/expiring")
async def list_expiring(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    days: int = Query(default=svc.EXPIRY_ALERT_DAYS, ge=0, le=365),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """Documents expired or expiring within ``days``.

    Drives the dashboard alert tile. Uses the partial index on
    ``expires_at`` so the scan stays tiny even at millions of rows.
    """
    org_id = _org(ctx)
    from datetime import timedelta
    cutoff = svc.now_utc() + timedelta(days=days)
    base = (
        select(Document)
        .where(
            Document.org_id == org_id,
            Document.expires_at.is_not(None),
            Document.expires_at <= cutoff,
        )
    )
    m = _member(ctx)
    if m.role == OrgRole.MEMBER:
        actor = _actor(ctx)
        base = base.where(
            or_(
                Document.is_shared == True,  # noqa: E712
                Document.uploaded_by == actor,
            )
        )

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    total_pages = (total + limit - 1) // limit if total > 0 else 0

    query = base.order_by(Document.expires_at.asc()).offset((page - 1) * limit).limit(limit)
    rows = (await db.execute(query)).scalars().all()
    return {
        "items": [DocumentOut.from_row(r) for r in rows],
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


@router.get("/linked/{linked_type}/{linked_id}")
async def list_linked(
    linked_type: str,
    linked_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """Documents attached to a specific supplier / customer / product."""
    try:
        ltype = svc.validate_linked_type(linked_type)
    except svc.DocumentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    org_id = _org(ctx)
    base = (
        select(Document)
        .where(
            Document.org_id == org_id,
            Document.linked_type == ltype,
            Document.linked_id == linked_id,
        )
    )
    m = _member(ctx)
    if m.role == OrgRole.MEMBER:
        actor = _actor(ctx)
        base = base.where(
            or_(
                Document.is_shared == True,  # noqa: E712
                Document.uploaded_by == actor,
            )
        )

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    total_pages = (total + limit - 1) // limit if total > 0 else 0

    query = base.order_by(Document.created_at.desc()).offset((page - 1) * limit).limit(limit)
    rows = (await db.execute(query)).scalars().all()
    return {
        "items": [DocumentOut.from_row(r) for r in rows],
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(
    doc_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    row = await _load(db, doc_id=doc_id, org_id=org_id)
    if not _can_view(row, ctx):
        raise HTTPException(status_code=404, detail="document_not_found")
    return DocumentOut.from_row(row)


@router.post("", response_model=DocumentOut, status_code=201)
async def create_document(
    body: DocumentCreateIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    row = Document(
        id=uuid.uuid4(),
        org_id=org_id,
        uploaded_by=_actor(ctx),
        name=body.name.strip(),
        category=svc.validate_category(body.category),
        file_url=body.file_url,
        file_size=body.file_size,
        mime_type=body.mime_type,
        tags=svc.normalise_tags(body.tags or []),
        linked_type=body.linked_type,
        linked_id=body.linked_id,
        expires_at=body.expires_at,
        is_shared=body.is_shared,
        description=body.description,
    )
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="document.uploaded",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="document",
        target_id=str(row.id),
        request=request,
        extra={
            "name": row.name,
            "category": row.category,
            "size": row.file_size,
            "mime": row.mime_type,
        },
    )
    await db.commit()
    await db.refresh(row)
    return DocumentOut.from_row(row)


@router.patch("/{doc_id}", response_model=DocumentOut)
async def update_document(
    doc_id: uuid.UUID,
    body: DocumentUpdateIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    row = await _load(db, doc_id=doc_id, org_id=org_id)
    if not _can_view(row, ctx):
        raise HTTPException(status_code=404, detail="document_not_found")
    m = _member(ctx)
    # MEMBERs can only edit their own uploads.
    if m.role == OrgRole.MEMBER and row.uploaded_by != _actor(ctx):
        raise HTTPException(status_code=403, detail="forbidden")

    payload = body.model_dump(exclude_unset=True)
    if "name" in payload and isinstance(payload["name"], str):
        payload["name"] = payload["name"].strip()
    if "category" in payload and payload["category"] is not None:
        payload["category"] = svc.validate_category(payload["category"])
    if "tags" in payload and payload["tags"] is not None:
        payload["tags"] = svc.normalise_tags(payload["tags"])

    for field in (
        "name", "category", "tags", "linked_type", "linked_id",
        "expires_at", "is_shared", "description",
    ):
        if field in payload:
            setattr(row, field, payload[field])

    await db.flush()
    await log_action(
        db,
        action="document.updated",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="document",
        target_id=str(row.id),
        request=request,
        extra={"fields": list(payload.keys())},
    )
    await db.commit()
    await db.refresh(row)
    return DocumentOut.from_row(row)


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Hard-delete a document row.

    GDPR-compliant: document content is customer-uploaded, not a
    bookkeeping verification, so a true delete is correct here
    (unlike invoice rows under bokföringslagen). The object-store
    reaper sweeps the ``file_url`` lazily in a follow-up.
    """
    org_id = _org(ctx)
    row = await _load(db, doc_id=doc_id, org_id=org_id)
    m = _member(ctx)
    # MEMBER can only delete own uploads; owner/admin can delete any.
    if m.role == OrgRole.MEMBER and row.uploaded_by != _actor(ctx):
        raise HTTPException(status_code=403, detail="forbidden")

    await db.delete(row)
    await db.flush()
    await log_action(
        db,
        action="document.deleted",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="document",
        target_id=str(doc_id),
        request=request,
        extra={"name": row.name, "category": row.category},
    )
    await db.commit()
