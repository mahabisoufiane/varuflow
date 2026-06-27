"""Market Expansion Checklist router — per-country expansion readiness."""
import logging
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.features.analytics.growth import MarketExpansionChecklist
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)
router = APIRouter(tags=["market-expansion"], dependencies=[Depends(require_module("analytics"))])

# Default checklist template per country (categories: Legal, Financial, Operations, Marketing, Technology)
_DEFAULT_ITEMS = [
    {"id": "legal_entity",    "category": "Legal",       "title": "Register legal entity in country",            "done": False, "notes": ""},
    {"id": "vat_reg",         "category": "Legal",       "title": "VAT/GST registration completed",              "done": False, "notes": ""},
    {"id": "bank_account",    "category": "Financial",   "title": "Local business bank account opened",           "done": False, "notes": ""},
    {"id": "currency",        "category": "Financial",   "title": "Multi-currency invoicing configured in app",   "done": False, "notes": ""},
    {"id": "tax_advisor",     "category": "Financial",   "title": "Local tax advisor engaged",                   "done": False, "notes": ""},
    {"id": "payment_method",  "category": "Financial",   "title": "Local preferred payment method supported",     "done": False, "notes": ""},
    {"id": "locale_ui",       "category": "Technology",  "title": "UI translated to local language",             "done": False, "notes": ""},
    {"id": "locale_docs",     "category": "Technology",  "title": "Invoice/document templates in local language", "done": False, "notes": ""},
    {"id": "data_residency",  "category": "Technology",  "title": "Data residency requirements verified",        "done": False, "notes": ""},
    {"id": "logistics",       "category": "Operations",  "title": "Local shipping / logistics partner arranged",  "done": False, "notes": ""},
    {"id": "warehouse",       "category": "Operations",  "title": "Local warehouse or 3PL identified",            "done": False, "notes": ""},
    {"id": "customer_support","category": "Operations",  "title": "Local customer support plan in place",         "done": False, "notes": ""},
    {"id": "marketing_plan",  "category": "Marketing",   "title": "Go-to-market plan created",                   "done": False, "notes": ""},
    {"id": "local_partner",   "category": "Marketing",   "title": "Local channel partner or reseller identified", "done": False, "notes": ""},
    {"id": "compliance_audit","category": "Legal",       "title": "GDPR / local privacy law compliance verified", "done": False, "notes": ""},
]

_COUNTRY_NAMES: dict[str, str] = {
    "NO": "Norway", "DK": "Denmark", "FI": "Finland", "DE": "Germany",
    "NL": "Netherlands", "PL": "Poland", "FR": "France", "GB": "United Kingdom",
    "ES": "Spain", "IT": "Italy", "US": "United States", "CA": "Canada",
    "AU": "Australia", "AE": "UAE", "SA": "Saudi Arabia", "SE": "Sweden",
}

_AVAILABLE_MARKETS = [
    {"code": "NO", "name": "Norway",          "currency": "NOK", "region": "Nordics"},
    {"code": "DK", "name": "Denmark",         "currency": "DKK", "region": "Nordics"},
    {"code": "FI", "name": "Finland",         "currency": "EUR", "region": "Nordics"},
    {"code": "DE", "name": "Germany",         "currency": "EUR", "region": "EU"},
    {"code": "NL", "name": "Netherlands",     "currency": "EUR", "region": "EU"},
    {"code": "PL", "name": "Poland",          "currency": "PLN", "region": "EU"},
    {"code": "FR", "name": "France",          "currency": "EUR", "region": "EU"},
    {"code": "GB", "name": "United Kingdom",  "currency": "GBP", "region": "Europe"},
    {"code": "US", "name": "United States",   "currency": "USD", "region": "Americas"},
    {"code": "AE", "name": "UAE",             "currency": "AED", "region": "MENA"},
    {"code": "SA", "name": "Saudi Arabia",    "currency": "SAR", "region": "MENA"},
]


class ChecklistCreate(BaseModel):
    country_code: str
    target_launch_date: date | None = None

class ItemUpdate(BaseModel):
    item_id: str
    done: bool
    notes: str = ""

class ChecklistPatch(BaseModel):
    target_launch_date: date | None = None


@router.get("/api/growth/expansion/markets")
async def available_markets(member=Depends(get_current_member)):
    """Return list of supported expansion markets."""
    return _AVAILABLE_MARKETS


@router.get("/api/growth/expansion/checklists")
async def list_checklists(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        rows = (await db.execute(
            select(MarketExpansionChecklist)
            .where(MarketExpansionChecklist.org_id == org_id)
            .order_by(MarketExpansionChecklist.country_name)
        )).scalars().all()
        return [_cl_dict(c) for c in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_checklists failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/growth/expansion/checklists", status_code=201)
async def create_checklist(
    body: ChecklistCreate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        country_code = body.country_code.upper()
        country_name = _COUNTRY_NAMES.get(country_code, country_code)

        existing = (await db.execute(
            select(MarketExpansionChecklist).where(
                MarketExpansionChecklist.org_id == org_id,
                MarketExpansionChecklist.country_code == country_code,
            )
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail=f"Checklist for {country_name} already exists")

        cl = MarketExpansionChecklist(
            org_id=org_id,
            country_code=country_code,
            country_name=country_name,
            items=[dict(item) for item in _DEFAULT_ITEMS],
            target_launch_date=body.target_launch_date,
        )
        db.add(cl)
        await db.commit()
        await db.refresh(cl)
        return _cl_dict(cl)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_checklist failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/growth/expansion/checklists/{checklist_id}")
async def get_checklist(
    checklist_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        cl = (await db.execute(
            select(MarketExpansionChecklist).where(
                MarketExpansionChecklist.id == checklist_id,
                MarketExpansionChecklist.org_id == org_id,
            )
        )).scalar_one_or_none()
        if not cl:
            raise HTTPException(status_code=404, detail="Checklist not found")
        return _cl_dict(cl)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_checklist failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/growth/expansion/checklists/{checklist_id}/item")
async def update_item(
    checklist_id: str,
    body: ItemUpdate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Toggle a single checklist item's done state."""
    try:
        org_id = member["org_id"]
        cl = (await db.execute(
            select(MarketExpansionChecklist).where(
                MarketExpansionChecklist.id == checklist_id,
                MarketExpansionChecklist.org_id == org_id,
            )
        )).scalar_one_or_none()
        if not cl:
            raise HTTPException(status_code=404, detail="Checklist not found")

        items = list(cl.items or [])
        for item in items:
            if item.get("id") == body.item_id:
                item["done"] = body.done
                item["notes"] = body.notes
                break
        else:
            raise HTTPException(status_code=404, detail="Item not found")

        done_count = sum(1 for i in items if i.get("done"))
        cl.items = items
        cl.completion_pct = Decimal(str(round(done_count / len(items) * 100, 2))) if items else Decimal("0")
        await db.commit()
        await db.refresh(cl)
        return _cl_dict(cl)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_item failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/growth/expansion/checklists/{checklist_id}")
async def patch_checklist(
    checklist_id: str,
    body: ChecklistPatch,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        cl = (await db.execute(
            select(MarketExpansionChecklist).where(
                MarketExpansionChecklist.id == checklist_id,
                MarketExpansionChecklist.org_id == org_id,
            )
        )).scalar_one_or_none()
        if not cl:
            raise HTTPException(status_code=404, detail="Checklist not found")
        if body.target_launch_date is not None:
            cl.target_launch_date = body.target_launch_date
        await db.commit()
        await db.refresh(cl)
        return _cl_dict(cl)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"patch_checklist failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/growth/expansion/checklists/{checklist_id}", status_code=204)
async def delete_checklist(
    checklist_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        cl = (await db.execute(
            select(MarketExpansionChecklist).where(
                MarketExpansionChecklist.id == checklist_id,
                MarketExpansionChecklist.org_id == org_id,
            )
        )).scalar_one_or_none()
        if not cl:
            raise HTTPException(status_code=404, detail="Checklist not found")
        await db.delete(cl)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_checklist failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


def _cl_dict(c: MarketExpansionChecklist) -> dict:
    items = c.items or []
    by_category: dict[str, list] = {}
    for item in items:
        cat = item.get("category", "Other")
        by_category.setdefault(cat, []).append(item)
    return {
        "id": str(c.id), "country_code": c.country_code, "country_name": c.country_name,
        "items": items, "items_by_category": by_category,
        "completion_pct": float(c.completion_pct),
        "done_count": sum(1 for i in items if i.get("done")),
        "total_count": len(items),
        "target_launch_date": c.target_launch_date.isoformat() if c.target_launch_date else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
