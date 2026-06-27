"""Branding endpoints — white-label customisation (ENTERPRISE only).

GET  /api/branding  — current org's branding (or defaults)
PUT  /api/branding  — update branding (owner-only, ENTERPRISE plan)
"""
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_feature
from app.features.portal.model_branding import OrgBranding
from app.features.auth.organization import OrgRole
from app.services.plan_limits import FEATURE_WHITE_LABEL

router = APIRouter(prefix="/api/branding", tags=["branding"])
log = logging.getLogger(__name__)

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")

DEFAULTS = {
    "app_name": "Varuflow",
    "logo_url": None,
    "favicon_url": None,
    "primary_color": "#6366f1",
    "accent_color": "#8b5cf6",
}


class BrandingOut(BaseModel):
    app_name: str
    logo_url: str | None
    favicon_url: str | None
    primary_color: str
    accent_color: str


class BrandingUpdate(BaseModel):
    app_name: str | None = None
    logo_url: str | None = None
    favicon_url: str | None = None
    primary_color: str | None = None
    accent_color: str | None = None

    @field_validator("primary_color", "accent_color", mode="before")
    @classmethod
    def validate_color(cls, v: str | None) -> str | None:
        if v is not None and not _HEX_COLOR.match(v):
            raise ValueError("Color must be a hex color (#RRGGBB)")
        return v


@router.get("", response_model=BrandingOut)
async def get_branding(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    row = await db.scalar(
        select(OrgBranding).where(OrgBranding.org_id == member.org_id)
    )
    if not row:
        return BrandingOut(**DEFAULTS)
    return BrandingOut(
        app_name=row.app_name or DEFAULTS["app_name"],
        logo_url=row.logo_url,
        favicon_url=row.favicon_url,
        primary_color=row.primary_color or DEFAULTS["primary_color"],
        accent_color=row.accent_color or DEFAULTS["accent_color"],
    )


@router.put("", response_model=BrandingOut)
async def update_branding(
    body: BrandingUpdate,
    ctx: tuple = Depends(get_current_member),
    _gate: None = Depends(require_feature(FEATURE_WHITE_LABEL)),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    if member.role != OrgRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the organization owner can update branding",
        )

    row = await db.scalar(
        select(OrgBranding).where(OrgBranding.org_id == member.org_id)
    )
    if not row:
        row = OrgBranding(org_id=member.org_id)
        db.add(row)

    if body.app_name is not None:
        row.app_name = body.app_name
    if body.logo_url is not None:
        row.logo_url = body.logo_url
    if body.favicon_url is not None:
        row.favicon_url = body.favicon_url
    if body.primary_color is not None:
        row.primary_color = body.primary_color
    if body.accent_color is not None:
        row.accent_color = body.accent_color

    await db.commit()
    await db.refresh(row)

    return BrandingOut(
        app_name=row.app_name or DEFAULTS["app_name"],
        logo_url=row.logo_url,
        favicon_url=row.favicon_url,
        primary_color=row.primary_color or DEFAULTS["primary_color"],
        accent_color=row.accent_color or DEFAULTS["accent_color"],
    )
