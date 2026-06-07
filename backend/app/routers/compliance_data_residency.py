"""Data residency selection per org

Endpoints:
  GET   /api/compliance/data-residency         get current setting
  PATCH /api/compliance/data-residency         update setting
  GET   /api/compliance/data-residency/regions list available regions + implications
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.organization import Organization
from app.services.audit_chain import write_audit_entry

router = APIRouter(prefix="/api/compliance/data-residency", tags=["compliance_data_residency"], dependencies=[Depends(require_module("compliance"))])
log = logging.getLogger(__name__)

REGIONS = {
    "eu": {
        "name": "European Union",
        "description": "Data processed and stored in EU data centres (Frankfurt/Stockholm). Required for GDPR compliance.",
        "frameworks": ["GDPR", "ISO 27001"],
        "countries": ["SE", "NO", "DK", "FI", "DE", "FR", "NL"],
    },
    "mena": {
        "name": "MENA",
        "description": "Data processed in UAE/KSA data centres. Required for UAE PDPL and Saudi PDPL compliance.",
        "frameworks": ["UAE PDPL", "Saudi PDPL", "ZATCA"],
        "countries": ["AE", "SA", "QA", "KW", "BH", "OM"],
    },
    "us": {
        "name": "United States",
        "description": "Data processed in US East/West data centres. For US-based subsidiaries.",
        "frameworks": ["SOC 2 Type II", "CCPA"],
        "countries": ["US"],
    },
    "apac": {
        "name": "Asia-Pacific",
        "description": "Data processed in Singapore/Sydney. For APAC subsidiaries.",
        "frameworks": ["PDPA (SG)", "APPs (AU)"],
        "countries": ["SG", "AU", "NZ", "JP"],
    },
}


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user(ctx: tuple) -> Optional[uuid.UUID]:
    _, member = ctx
    return member.user_id if hasattr(member, "user_id") else None


class PatchRegion(BaseModel):
    data_region: str
    acknowledged: bool = False   # must pass true to confirm the implications


@router.get("/regions")
async def list_regions():
    """Return all available regions with their compliance frameworks."""
    return {"regions": [{"id": k, **v} for k, v in REGIONS.items()]}


@router.get("")
async def get_data_residency(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        row = await db.execute(select(Organization).where(Organization.id == org_id))
        org = row.scalar_one_or_none()
        if not org:
            raise HTTPException(status_code=404, detail="Organisation not found")
        current = getattr(org, "data_region", "eu") or "eu"
        return {
            "data_region": current,
            "region_info": REGIONS.get(current, {}),
            "name": org.name,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_data_residency failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("")
async def update_data_residency(
    body: PatchRegion,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        if body.data_region not in REGIONS:
            raise HTTPException(status_code=422, detail=f"data_region must be one of {list(REGIONS.keys())}")
        if not body.acknowledged:
            raise HTTPException(
                status_code=422,
                detail="Set acknowledged=true to confirm you understand data region implications. "
                       "Changing regions does not automatically migrate existing data.",
            )
        row = await db.execute(select(Organization).where(Organization.id == org_id))
        org = row.scalar_one_or_none()
        if not org:
            raise HTTPException(status_code=404, detail="Organisation not found")

        old_region = getattr(org, "data_region", "eu") or "eu"
        org.data_region = body.data_region

        # Audit the region change
        await write_audit_entry(
            db,
            org_id=org_id,
            actor_user_id=_user(ctx),
            action="data_residency.changed",
            target_type="organization",
            target_id=str(org_id),
            extra={"from": old_region, "to": body.data_region},
        )

        await db.commit()
        return {
            "data_region": org.data_region,
            "region_info": REGIONS.get(org.data_region, {}),
            "warning": (
                "Data region updated. Note: existing data is NOT automatically moved to the new region. "
                "Contact support to initiate a data migration if required for compliance."
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_data_residency failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
