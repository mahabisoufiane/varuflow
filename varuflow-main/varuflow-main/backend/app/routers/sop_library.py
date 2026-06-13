"""SOP Library — Standard Operating Procedure documents with versioning.

Endpoints
─────────
GET    /api/sop/categories              → distinct categories for org
GET    /api/sop                         → list documents
POST   /api/sop                         → create document
GET    /api/sop/{id}                    → detail + version history
PATCH  /api/sop/{id}                    → update (snapshots version on content change)
DELETE /api/sop/{id}                    → delete (not published)
POST   /api/sop/{id}/publish            → publish
POST   /api/sop/{id}/archive            → archive
GET    /api/sop/{id}/versions/{ver}     → historical version content
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.sop import SopDocument, SopVersion

router = APIRouter(prefix="/api/sop", tags=["sop"])
log = logging.getLogger(__name__)

_VALID_STATUSES = {"draft", "published", "archived"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    user, _ = ctx
    return uuid.UUID(str(user["user_id"]))


def _slugify(title: str) -> str:
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:100]


def _doc_list_out(doc: SopDocument) -> dict[str, Any]:
    return {
        "id": str(doc.id),
        "title": doc.title,
        "slug": doc.slug,
        "category": doc.category,
        "version": doc.version,
        "status": doc.status,
        "published_at": doc.published_at.isoformat() if doc.published_at else None,
        "created_at": doc.created_at.isoformat(),
    }


def _doc_detail_out(doc: SopDocument, version_history: list[SopVersion]) -> dict[str, Any]:
    d = _doc_list_out(doc)
    d["content_markdown"] = doc.content_markdown
    d["created_by"] = str(doc.created_by) if doc.created_by else None
    d["updated_at"] = doc.updated_at.isoformat()
    d["version_history"] = [
        {
            "id": str(v.id),
            "version": v.version,
            "change_notes": v.change_notes,
            "changed_by": str(v.changed_by) if v.changed_by else None,
            "created_at": v.created_at.isoformat(),
        }
        for v in version_history
    ]
    return d


# ── Schemas ────────────────────────────────────────────────────────────────────

class SopDocIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    slug: Optional[str] = Field(default=None, max_length=100)
    category: Optional[str] = Field(default=None, max_length=100)
    content_markdown: Optional[str] = None


class SopDocPatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=300)
    category: Optional[str] = Field(default=None, max_length=100)
    content_markdown: Optional[str] = None
    status: Optional[str] = None
    change_notes: Optional[str] = Field(default=None, max_length=500)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/categories")
async def list_categories(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Distinct categories for the org (for filter dropdown)."""
    org_id = _org_id(ctx)
    try:
        rows = (await db.execute(
            select(SopDocument.category)
            .where(SopDocument.org_id == org_id, SopDocument.category.isnot(None))
            .distinct()
            .order_by(SopDocument.category)
        )).scalars().all()
        return [r for r in rows if r]
    except Exception as e:
        log.error("list_categories failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("")
async def list_sop_documents(
    category: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = select(SopDocument).where(SopDocument.org_id == org_id)
        if category:
            q = q.where(SopDocument.category == category)
        if status:
            q = q.where(SopDocument.status == status)
        q = q.order_by(SopDocument.created_at)
        docs = (await db.execute(q)).scalars().all()
        return [_doc_list_out(d) for d in docs]
    except Exception as e:
        log.error("list_sop_documents failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_sop_document(
    body: SopDocIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    try:
        slug = body.slug.strip() if body.slug else _slugify(body.title)
        if not slug:
            slug = _slugify(body.title)

        existing = await db.scalar(
            select(SopDocument).where(
                SopDocument.org_id == org_id, SopDocument.slug == slug
            )
        )
        if existing:
            raise HTTPException(status_code=409, detail="A document with this slug already exists for your organisation")

        doc = SopDocument(
            org_id=org_id,
            title=body.title,
            slug=slug,
            category=body.category,
            content_markdown=body.content_markdown,
            version=1,
            status="draft",
            created_by=user_id,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        return _doc_list_out(doc)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_sop_document failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{doc_id}")
async def get_sop_document(
    doc_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        doc = await db.scalar(
            select(SopDocument).where(
                SopDocument.id == doc_id, SopDocument.org_id == org_id
            )
        )
        if not doc:
            raise HTTPException(status_code=404, detail="SOP document not found")

        versions = (await db.execute(
            select(SopVersion)
            .where(SopVersion.sop_id == doc_id)
            .order_by(SopVersion.version.desc())
        )).scalars().all()

        return _doc_detail_out(doc, versions)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_sop_document failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{doc_id}")
async def patch_sop_document(
    doc_id: uuid.UUID,
    body: SopDocPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    try:
        doc = await db.scalar(
            select(SopDocument).where(
                SopDocument.id == doc_id, SopDocument.org_id == org_id
            )
        )
        if not doc:
            raise HTTPException(status_code=404, detail="SOP document not found")

        content_changed = (
            body.content_markdown is not None
            and body.content_markdown != doc.content_markdown
        )

        if content_changed:
            # Snapshot old version before overwriting
            snapshot = SopVersion(
                sop_id=doc_id,
                version=doc.version,
                content_markdown=doc.content_markdown,
                changed_by=user_id,
                change_notes=body.change_notes,
            )
            db.add(snapshot)
            doc.version = doc.version + 1
            doc.content_markdown = body.content_markdown

        if body.title is not None:
            doc.title = body.title
        if body.category is not None:
            doc.category = body.category
        if body.status is not None:
            if body.status not in _VALID_STATUSES:
                raise HTTPException(
                    status_code=422,
                    detail=f"status must be one of {_VALID_STATUSES}",
                )
            doc.status = body.status

        doc.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(doc)

        versions = (await db.execute(
            select(SopVersion)
            .where(SopVersion.sop_id == doc_id)
            .order_by(SopVersion.version.desc())
        )).scalars().all()

        return _doc_detail_out(doc, versions)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_sop_document failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{doc_id}", status_code=204)
async def delete_sop_document(
    doc_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        doc = await db.scalar(
            select(SopDocument).where(
                SopDocument.id == doc_id, SopDocument.org_id == org_id
            )
        )
        if not doc:
            raise HTTPException(status_code=404, detail="SOP document not found")
        if doc.status == "published":
            raise HTTPException(
                status_code=409,
                detail="Cannot delete a published document. Archive it first.",
            )
        await db.delete(doc)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_sop_document failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{doc_id}/publish", status_code=200)
async def publish_sop_document(
    doc_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        doc = await db.scalar(
            select(SopDocument).where(
                SopDocument.id == doc_id, SopDocument.org_id == org_id
            )
        )
        if not doc:
            raise HTTPException(status_code=404, detail="SOP document not found")
        if doc.status == "published":
            raise HTTPException(status_code=409, detail="Document is already published")
        doc.status = "published"
        doc.published_at = datetime.now(timezone.utc)
        doc.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(doc)
        return _doc_list_out(doc)
    except HTTPException:
        raise
    except Exception as e:
        log.error("publish_sop_document failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{doc_id}/archive", status_code=200)
async def archive_sop_document(
    doc_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        doc = await db.scalar(
            select(SopDocument).where(
                SopDocument.id == doc_id, SopDocument.org_id == org_id
            )
        )
        if not doc:
            raise HTTPException(status_code=404, detail="SOP document not found")
        doc.status = "archived"
        doc.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(doc)
        return _doc_list_out(doc)
    except HTTPException:
        raise
    except Exception as e:
        log.error("archive_sop_document failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{doc_id}/versions/{version_num}")
async def get_sop_version(
    doc_id: uuid.UUID,
    version_num: int,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        doc = await db.scalar(
            select(SopDocument).where(
                SopDocument.id == doc_id, SopDocument.org_id == org_id
            )
        )
        if not doc:
            raise HTTPException(status_code=404, detail="SOP document not found")

        ver = await db.scalar(
            select(SopVersion).where(
                SopVersion.sop_id == doc_id,
                SopVersion.version == version_num,
            )
        )
        if not ver:
            raise HTTPException(status_code=404, detail="Version not found")

        return {
            "id": str(ver.id),
            "sop_id": str(ver.sop_id),
            "version": ver.version,
            "content_markdown": ver.content_markdown,
            "change_notes": ver.change_notes,
            "changed_by": str(ver.changed_by) if ver.changed_by else None,
            "created_at": ver.created_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_sop_version failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
