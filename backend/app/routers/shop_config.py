"""Admin router for storefront configuration.

Requires auth (OWNER or ADMIN role). One storefront per org.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.ecommerce import Storefront
from app.models.organization import OrgRole

log = logging.getLogger(__name__)

router = APIRouter()

_VALID_SLUG = re.compile(r"^[a-z0-9-]{2,80}$")

ALLOWED_ROLES = {OrgRole.OWNER, OrgRole.ADMIN}


def _sf_out(sf: Storefront) -> dict:
    return {
        "id": str(sf.id),
        "slug": sf.slug,
        "name": sf.name,
        "tagline": sf.tagline,
        "logo_url": sf.logo_url,
        "primary_color": sf.primary_color,
        "is_active": sf.is_active,
        "payment_methods": sf.payment_methods.split(","),
        "currency": sf.currency,
        "created_at": sf.created_at.isoformat(),
        "updated_at": sf.updated_at.isoformat(),
    }


def _slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[åä]", "a", slug)
    slug = re.sub(r"[ö]", "o", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:80] or "shop"


@router.get("/api/shop/config")
async def get_config(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _, member = ctx
        sf = (
            await db.execute(
                select(Storefront).where(Storefront.org_id == member.org_id)
            )
        ).scalar_one_or_none()
        if not sf:
            raise HTTPException(status_code=404, detail="No storefront configured")
        return _sf_out(sf)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_config failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


class CreateStorefrontBody(BaseModel):
    name: str
    slug: Optional[str] = None
    tagline: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    payment_methods: Optional[str] = "card"
    currency: str = "SEK"


@router.post("/api/shop/config", status_code=201)
async def create_config(
    body: CreateStorefrontBody,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _, member = ctx
        if member.role not in ALLOWED_ROLES:
            raise HTTPException(status_code=403, detail="Only OWNER or ADMIN can create a storefront")

        existing = (
            await db.execute(
                select(Storefront).where(Storefront.org_id == member.org_id)
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Storefront already exists")

        slug = body.slug or _slugify(body.name)
        if not _VALID_SLUG.match(slug):
            raise HTTPException(status_code=422, detail="Slug must be 2-80 lowercase letters, digits, or hyphens")

        # Check slug uniqueness
        conflict = (
            await db.execute(select(Storefront).where(Storefront.slug == slug))
        ).scalar_one_or_none()
        if conflict:
            slug = f"{slug}-{str(uuid.uuid4())[:8]}"

        sf = Storefront(
            org_id=member.org_id,
            slug=slug,
            name=body.name,
            tagline=body.tagline,
            logo_url=body.logo_url,
            primary_color=body.primary_color,
            payment_methods=body.payment_methods or "card",
            currency=body.currency.upper(),
            is_active=False,
        )
        db.add(sf)
        await db.commit()
        await db.refresh(sf)
        return _sf_out(sf)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_config failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


class PatchStorefrontBody(BaseModel):
    name: Optional[str] = None
    tagline: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    payment_methods: Optional[str] = None
    currency: Optional[str] = None
    is_active: Optional[bool] = None


@router.patch("/api/shop/config")
async def patch_config(
    body: PatchStorefrontBody,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _, member = ctx
        if member.role not in ALLOWED_ROLES:
            raise HTTPException(status_code=403, detail="Only OWNER or ADMIN can update a storefront")

        sf = (
            await db.execute(
                select(Storefront).where(Storefront.org_id == member.org_id)
            )
        ).scalar_one_or_none()
        if not sf:
            raise HTTPException(status_code=404, detail="No storefront configured")

        if body.name is not None:
            sf.name = body.name
        if body.tagline is not None:
            sf.tagline = body.tagline
        if body.logo_url is not None:
            sf.logo_url = body.logo_url
        if body.primary_color is not None:
            sf.primary_color = body.primary_color
        if body.payment_methods is not None:
            sf.payment_methods = body.payment_methods
        if body.currency is not None:
            sf.currency = body.currency.upper()
        if body.is_active is not None:
            sf.is_active = body.is_active

        await db.commit()
        await db.refresh(sf)
        return _sf_out(sf)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_config failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
