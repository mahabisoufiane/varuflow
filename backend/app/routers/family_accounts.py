"""Family accounts router — manage family groups and their members.

Endpoints
─────────
GET    /api/family                          → list family groups for org
POST   /api/family                          → create family group
GET    /api/family/{id}                     → detail with members
PATCH  /api/family/{id}                     → update name / shared_loyalty
DELETE /api/family/{id}                     → delete group
POST   /api/family/{id}/members             → add member to group
DELETE /api/family/{id}/members/{member_id} → remove member
"""
from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.family_group import FamilyGroup, FamilyMember

router = APIRouter(prefix="/api/family", tags=["family-accounts"])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _member_out(m: FamilyMember) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "family_group_id": str(m.family_group_id),
        "customer_id": str(m.customer_id) if m.customer_id else None,
        "name": m.name,
        "date_of_birth": m.date_of_birth.isoformat() if m.date_of_birth else None,
        "relationship": m.relationship,
        "created_at": m.created_at.isoformat(),
    }


def _group_out(g: FamilyGroup, member_count: int = 0) -> dict[str, Any]:
    return {
        "id": str(g.id),
        "org_id": str(g.org_id),
        "primary_customer_id": str(g.primary_customer_id),
        "name": g.name,
        "shared_loyalty": g.shared_loyalty,
        "member_count": member_count,
        "created_at": g.created_at.isoformat(),
    }


def _group_detail_out(g: FamilyGroup, members: list[FamilyMember]) -> dict[str, Any]:
    d = _group_out(g, len(members))
    d["members"] = [_member_out(m) for m in members]
    return d


# ── Schemas ────────────────────────────────────────────────────────────────────

class FamilyGroupIn(BaseModel):
    primary_customer_id: uuid.UUID
    name: Optional[str] = Field(default=None, max_length=200)
    shared_loyalty: bool = True


class FamilyGroupPatch(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    shared_loyalty: Optional[bool] = None


class FamilyMemberIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    customer_id: Optional[uuid.UUID] = None
    date_of_birth: Optional[date] = None
    relationship: Optional[str] = Field(default=None, max_length=50)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_family_groups(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        groups = (await db.execute(
            select(FamilyGroup)
            .where(FamilyGroup.org_id == org_id)
            .order_by(FamilyGroup.created_at)
        )).scalars().all()

        results = []
        for g in groups:
            count = (await db.scalar(
                select(func.count(FamilyMember.id))
                .where(FamilyMember.family_group_id == g.id)
            )) or 0
            results.append(_group_out(g, count))
        return results
    except Exception as e:
        log.error("list_family_groups failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_family_group(
    body: FamilyGroupIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        group = FamilyGroup(
            org_id=org_id,
            primary_customer_id=body.primary_customer_id,
            name=body.name,
            shared_loyalty=body.shared_loyalty,
        )
        db.add(group)
        await db.commit()
        await db.refresh(group)
        return _group_out(group, 0)
    except Exception as e:
        log.error("create_family_group failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{group_id}")
async def get_family_group(
    group_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        group = await db.scalar(
            select(FamilyGroup).where(
                FamilyGroup.id == group_id, FamilyGroup.org_id == org_id
            )
        )
        if not group:
            raise HTTPException(status_code=404, detail="Family group not found")

        members = (await db.execute(
            select(FamilyMember)
            .where(FamilyMember.family_group_id == group_id)
            .order_by(FamilyMember.created_at)
        )).scalars().all()

        return _group_detail_out(group, list(members))
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_family_group failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{group_id}")
async def update_family_group(
    group_id: uuid.UUID,
    body: FamilyGroupPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        group = await db.scalar(
            select(FamilyGroup).where(
                FamilyGroup.id == group_id, FamilyGroup.org_id == org_id
            )
        )
        if not group:
            raise HTTPException(status_code=404, detail="Family group not found")

        if body.name is not None:
            group.name = body.name
        if body.shared_loyalty is not None:
            group.shared_loyalty = body.shared_loyalty

        await db.commit()
        await db.refresh(group)

        count = (await db.scalar(
            select(func.count(FamilyMember.id))
            .where(FamilyMember.family_group_id == group_id)
        )) or 0
        return _group_out(group, count)
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_family_group failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{group_id}", status_code=204)
async def delete_family_group(
    group_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        group = await db.scalar(
            select(FamilyGroup).where(
                FamilyGroup.id == group_id, FamilyGroup.org_id == org_id
            )
        )
        if not group:
            raise HTTPException(status_code=404, detail="Family group not found")
        await db.delete(group)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_family_group failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{group_id}/members", status_code=201)
async def add_family_member(
    group_id: uuid.UUID,
    body: FamilyMemberIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        group = await db.scalar(
            select(FamilyGroup).where(
                FamilyGroup.id == group_id, FamilyGroup.org_id == org_id
            )
        )
        if not group:
            raise HTTPException(status_code=404, detail="Family group not found")

        member = FamilyMember(
            family_group_id=group_id,
            customer_id=body.customer_id,
            name=body.name,
            date_of_birth=body.date_of_birth,
            relationship=body.relationship,
        )
        db.add(member)
        await db.commit()
        await db.refresh(member)
        return _member_out(member)
    except HTTPException:
        raise
    except Exception as e:
        log.error("add_family_member failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{group_id}/members/{member_id}", status_code=204)
async def remove_family_member(
    group_id: uuid.UUID,
    member_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        # Verify the group belongs to this org
        group = await db.scalar(
            select(FamilyGroup).where(
                FamilyGroup.id == group_id, FamilyGroup.org_id == org_id
            )
        )
        if not group:
            raise HTTPException(status_code=404, detail="Family group not found")

        member = await db.scalar(
            select(FamilyMember).where(
                FamilyMember.id == member_id,
                FamilyMember.family_group_id == group_id,
            )
        )
        if not member:
            raise HTTPException(status_code=404, detail="Family member not found")

        await db.delete(member)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("remove_family_member failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
