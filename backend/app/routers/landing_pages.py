"""Landing pages — publishable marketing pages with lead capture.

Endpoints
─────────
GET    /api/landing-pages           → list
POST   /api/landing-pages           → create (auto-slugify title if no slug)
GET    /api/landing-pages/{id}      → detail
PATCH  /api/landing-pages/{id}      → update
DELETE /api/landing-pages/{id}      → delete
POST   /api/landing-pages/{id}/publish  → publish
GET    /api/landing-pages/{id}/stats    → view stats
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.landing_page import LandingPage

router = APIRouter(prefix="/api/landing-pages", tags=["landing-pages"])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    slug = slug.strip("-")
    return slug[:100]


def _page_out(p: LandingPage) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "org_id": str(p.org_id),
        "title": p.title,
        "slug": p.slug,
        "headline": p.headline,
        "subheadline": p.subheadline,
        "cta_text": p.cta_text,
        "cta_url": p.cta_url,
        "body_html": p.body_html,
        "lead_form_id": str(p.lead_form_id) if p.lead_form_id else None,
        "status": p.status,
        "view_count": p.view_count,
        "published_at": p.published_at.isoformat() if p.published_at else None,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class PageIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    slug: Optional[str] = Field(default=None, max_length=100)
    headline: Optional[str] = Field(default=None, max_length=300)
    subheadline: Optional[str] = None
    cta_text: Optional[str] = Field(default=None, max_length=100)
    cta_url: Optional[str] = Field(default=None, max_length=500)
    body_html: Optional[str] = None
    lead_form_id: Optional[uuid.UUID] = None


class PagePatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=300)
    slug: Optional[str] = Field(default=None, max_length=100)
    headline: Optional[str] = Field(default=None, max_length=300)
    subheadline: Optional[str] = None
    cta_text: Optional[str] = Field(default=None, max_length=100)
    cta_url: Optional[str] = Field(default=None, max_length=500)
    body_html: Optional[str] = None
    lead_form_id: Optional[uuid.UUID] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_pages(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        rows = (await db.execute(
            select(LandingPage).where(LandingPage.org_id == org_id).order_by(LandingPage.created_at.desc())
        )).scalars().all()
        return [_page_out(p) for p in rows]
    except Exception as e:
        log.error("list_pages failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_page(
    body: PageIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        slug = body.slug if body.slug else _slugify(body.title)

        # Check slug uniqueness for org
        existing = await db.scalar(
            select(LandingPage).where(LandingPage.org_id == org_id, LandingPage.slug == slug)
        )
        if existing:
            raise HTTPException(status_code=409, detail="A landing page with this slug already exists")

        p = LandingPage(
            org_id=org_id,
            title=body.title,
            slug=slug,
            headline=body.headline,
            subheadline=body.subheadline,
            cta_text=body.cta_text,
            cta_url=body.cta_url,
            body_html=body.body_html,
            lead_form_id=body.lead_form_id,
        )
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return _page_out(p)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_page failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{page_id}")
async def get_page(
    page_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        p = await db.scalar(
            select(LandingPage).where(LandingPage.id == page_id, LandingPage.org_id == org_id)
        )
        if not p:
            raise HTTPException(status_code=404, detail="Landing page not found")
        return _page_out(p)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_page failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{page_id}")
async def patch_page(
    page_id: uuid.UUID,
    body: PagePatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        p = await db.scalar(
            select(LandingPage).where(LandingPage.id == page_id, LandingPage.org_id == org_id)
        )
        if not p:
            raise HTTPException(status_code=404, detail="Landing page not found")

        if body.title is not None:
            p.title = body.title
        if body.slug is not None:
            # Check new slug uniqueness
            existing = await db.scalar(
                select(LandingPage).where(
                    LandingPage.org_id == org_id,
                    LandingPage.slug == body.slug,
                    LandingPage.id != page_id,
                )
            )
            if existing:
                raise HTTPException(status_code=409, detail="A landing page with this slug already exists")
            p.slug = body.slug
        if body.headline is not None:
            p.headline = body.headline
        if body.subheadline is not None:
            p.subheadline = body.subheadline
        if body.cta_text is not None:
            p.cta_text = body.cta_text
        if body.cta_url is not None:
            p.cta_url = body.cta_url
        if body.body_html is not None:
            p.body_html = body.body_html
        if body.lead_form_id is not None:
            p.lead_form_id = body.lead_form_id

        p.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(p)
        return _page_out(p)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_page failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{page_id}", status_code=204)
async def delete_page(
    page_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        p = await db.scalar(
            select(LandingPage).where(LandingPage.id == page_id, LandingPage.org_id == org_id)
        )
        if not p:
            raise HTTPException(status_code=404, detail="Landing page not found")
        await db.delete(p)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_page failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{page_id}/publish")
async def publish_page(
    page_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        p = await db.scalar(
            select(LandingPage).where(LandingPage.id == page_id, LandingPage.org_id == org_id)
        )
        if not p:
            raise HTTPException(status_code=404, detail="Landing page not found")
        p.status = "published"
        p.published_at = datetime.now(timezone.utc)
        p.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(p)
        return _page_out(p)
    except HTTPException:
        raise
    except Exception as e:
        log.error("publish_page failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{page_id}/stats")
async def page_stats(
    page_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        p = await db.scalar(
            select(LandingPage).where(LandingPage.id == page_id, LandingPage.org_id == org_id)
        )
        if not p:
            raise HTTPException(status_code=404, detail="Landing page not found")
        return {
            "id": str(p.id),
            "title": p.title,
            "slug": p.slug,
            "status": p.status,
            "view_count": p.view_count,
            "lead_form_id": str(p.lead_form_id) if p.lead_form_id else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("page_stats failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
