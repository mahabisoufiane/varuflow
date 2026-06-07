"""Knowledge base router (Sprint 11) — prefix /api/kb."""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.knowledge_base import KbArticle, KbCategory
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kb", tags=["knowledge-base"], dependencies=[Depends(require_module("hr"))])


# ── Schemas ───────────────────────────────────────────────────────────────────

class KbCategoryOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    sort_order: int
    created_at: datetime

    class Config:
        from_attributes = True


class CreateCategoryIn(BaseModel):
    name: str = Field(..., max_length=100)
    sort_order: int = 0


class KbArticleOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    category_id: Optional[uuid.UUID]
    title: str
    slug: str
    body: str
    is_published: bool
    view_count: int
    helpful_count: int
    not_helpful_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CreateArticleIn(BaseModel):
    category_id: Optional[uuid.UUID] = None
    title: str = Field(..., max_length=300)
    slug: Optional[str] = Field(default=None, max_length=300)
    body: str
    is_published: bool = True


class UpdateArticleIn(BaseModel):
    category_id: Optional[uuid.UUID] = None
    title: Optional[str] = Field(default=None, max_length=300)
    slug: Optional[str] = Field(default=None, max_length=300)
    body: Optional[str] = None
    is_published: Optional[bool] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text)
    return text.strip("-")


# ── Categories ────────────────────────────────────────────────────────────────

@router.get("/categories", response_model=list[KbCategoryOut])
async def list_categories(
    org_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """PUBLIC — no auth required when org_id is provided."""
    try:
        rows = (
            await db.execute(
                select(KbCategory)
                .where(KbCategory.org_id == org_id)
                .order_by(KbCategory.sort_order.asc(), KbCategory.name.asc())
            )
        ).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_categories failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/categories", response_model=KbCategoryOut, status_code=201)
async def create_category(
    body: CreateCategoryIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        cat = KbCategory(org_id=org_id, name=body.name, sort_order=body.sort_order)
        db.add(cat)
        await db.commit()
        await db.refresh(cat)
        return cat
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_category failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/categories/{category_id}", status_code=204)
async def delete_category(
    category_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        cat = await db.get(KbCategory, category_id)
        if not cat or cat.org_id != org_id:
            raise HTTPException(status_code=404, detail="Category not found")
        await db.delete(cat)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_category failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Articles ──────────────────────────────────────────────────────────────────

@router.get("/articles", response_model=list[KbArticleOut])
async def list_articles(
    org_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    category_id: Optional[uuid.UUID] = Query(default=None),
    search: Optional[str] = Query(default=None),
    published_only: bool = Query(default=True),
):
    """PUBLIC — no auth required when org_id is provided."""
    try:
        q = select(KbArticle).where(KbArticle.org_id == org_id)
        if category_id:
            q = q.where(KbArticle.category_id == category_id)
        if published_only:
            q = q.where(KbArticle.is_published.is_(True))
        if search:
            term = f"%{search}%"
            q = q.where(KbArticle.title.ilike(term) | KbArticle.body.ilike(term))
        q = q.order_by(KbArticle.created_at.desc())
        rows = (await db.execute(q)).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_articles failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/articles", response_model=KbArticleOut, status_code=201)
async def create_article(
    body: CreateArticleIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        slug = body.slug or _slugify(body.title)
        article = KbArticle(
            org_id=org_id,
            category_id=body.category_id,
            title=body.title,
            slug=slug,
            body=body.body,
            is_published=body.is_published,
        )
        db.add(article)
        await db.commit()
        await db.refresh(article)
        return article
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_article failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/articles/{article_id}", response_model=KbArticleOut)
async def get_article(
    article_id: uuid.UUID,
    org_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """PUBLIC — increments view_count on each fetch."""
    try:
        article = await db.get(KbArticle, article_id)
        if not article or article.org_id != org_id:
            raise HTTPException(status_code=404, detail="Article not found")
        article.view_count = (article.view_count or 0) + 1
        await db.commit()
        await db.refresh(article)
        return article
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_article failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/articles/{article_id}", response_model=KbArticleOut)
async def update_article(
    article_id: uuid.UUID,
    body: UpdateArticleIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        article = await db.get(KbArticle, article_id)
        if not article or article.org_id != org_id:
            raise HTTPException(status_code=404, detail="Article not found")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(article, field, value)
        article.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(article)
        return article
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_article failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/articles/{article_id}", status_code=204)
async def delete_article(
    article_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        article = await db.get(KbArticle, article_id)
        if not article or article.org_id != org_id:
            raise HTTPException(status_code=404, detail="Article not found")
        await db.delete(article)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_article failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/articles/{article_id}/helpful", status_code=204)
async def mark_helpful(
    article_id: uuid.UUID,
    org_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """PUBLIC — increments helpful_count."""
    try:
        article = await db.get(KbArticle, article_id)
        if not article or article.org_id != org_id:
            raise HTTPException(status_code=404, detail="Article not found")
        article.helpful_count = (article.helpful_count or 0) + 1
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"mark_helpful failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/articles/{article_id}/not-helpful", status_code=204)
async def mark_not_helpful(
    article_id: uuid.UUID,
    org_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """PUBLIC — increments not_helpful_count."""
    try:
        article = await db.get(KbArticle, article_id)
        if not article or article.org_id != org_id:
            raise HTTPException(status_code=404, detail="Article not found")
        article.not_helpful_count = (article.not_helpful_count or 0) + 1
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"mark_not_helpful failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
