"""Policy Documents router — company policies accessible to all staff."""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.governance import PolicyDocument
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)
router = APIRouter(tags=["policy-docs"], dependencies=[Depends(require_module("settings"))])

_CATEGORIES = {"hr", "finance", "it", "legal", "operations", "security", "other"}
_EDIT_ROLES = {"OWNER", "ADMIN"}


class DocCreate(BaseModel):
    title: str
    category: str = "other"
    content: str = ""
    is_published: bool = False

class DocUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    content: str | None = None
    is_published: bool | None = None


@router.get("/api/governance/policies")
async def list_policies(
    category: str | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        role = member.get("role", "MEMBER")
        q = select(PolicyDocument).where(PolicyDocument.org_id == org_id)
        # Non-editors only see published docs
        if role not in _EDIT_ROLES:
            q = q.where(PolicyDocument.is_published == True)
        if category:
            q = q.where(PolicyDocument.category == category)
        rows = (await db.execute(q.order_by(PolicyDocument.category, PolicyDocument.title))).scalars().all()
        return [_doc_dict(d, include_content=False) for d in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_policies failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/governance/policies/categories")
async def list_categories(member=Depends(get_current_member)):
    return [
        {"value": "hr",         "label": "Human Resources"},
        {"value": "finance",    "label": "Finance & Expenses"},
        {"value": "it",         "label": "IT & Security"},
        {"value": "legal",      "label": "Legal & Compliance"},
        {"value": "operations", "label": "Operations"},
        {"value": "security",   "label": "Information Security"},
        {"value": "other",      "label": "Other"},
    ]


@router.get("/api/governance/policies/{doc_id}")
async def get_policy(
    doc_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        role = member.get("role", "MEMBER")
        doc = (await db.execute(
            select(PolicyDocument).where(PolicyDocument.id == doc_id, PolicyDocument.org_id == org_id)
        )).scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Policy not found")
        if not doc.is_published and role not in _EDIT_ROLES:
            raise HTTPException(status_code=403, detail="Policy not published")
        return _doc_dict(doc, include_content=True)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_policy failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/governance/policies", status_code=201)
async def create_policy(
    body: DocCreate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        _require_editor(member)
        if body.category not in _CATEGORIES:
            raise HTTPException(status_code=422, detail=f"Category must be one of {_CATEGORIES}")
        doc = PolicyDocument(
            org_id=org_id, title=body.title, category=body.category,
            content=body.content, is_published=body.is_published,
            created_by=member.get("user_id"), updated_by=member.get("user_id"),
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        return _doc_dict(doc, include_content=True)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_policy failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/governance/policies/{doc_id}")
async def update_policy(
    doc_id: str,
    body: DocUpdate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        _require_editor(member)
        doc = (await db.execute(
            select(PolicyDocument).where(PolicyDocument.id == doc_id, PolicyDocument.org_id == org_id)
        )).scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Policy not found")
        data = body.model_dump(exclude_none=True)
        if "category" in data and data["category"] not in _CATEGORIES:
            raise HTTPException(status_code=422, detail=f"Category must be one of {_CATEGORIES}")
        for field, val in data.items():
            setattr(doc, field, val)
        if data:
            doc.version = (doc.version or 1) + 1
            doc.updated_by = member.get("user_id")
        await db.commit()
        await db.refresh(doc)
        return _doc_dict(doc, include_content=True)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_policy failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/governance/policies/{doc_id}", status_code=204)
async def delete_policy(
    doc_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        if member.get("role") != "OWNER":
            raise HTTPException(status_code=403, detail="Only the org owner can delete policies")
        doc = (await db.execute(
            select(PolicyDocument).where(PolicyDocument.id == doc_id, PolicyDocument.org_id == org_id)
        )).scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="Policy not found")
        await db.delete(doc)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_policy failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


def _require_editor(member: dict) -> None:
    if member.get("role") not in _EDIT_ROLES:
        raise HTTPException(status_code=403, detail="Only Owner or Admin can manage policies")


def _doc_dict(d: PolicyDocument, include_content: bool = True) -> dict:
    result = {
        "id": str(d.id), "title": d.title, "category": d.category,
        "is_published": d.is_published, "version": d.version,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }
    if include_content:
        result["content"] = d.content
    return result
