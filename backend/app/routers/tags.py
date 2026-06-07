"""Tag manager router (Item 60).

Endpoints
---------

Tag catalogue (per-org)
    POST   /api/tags
    GET    /api/tags
    DELETE /api/tags/{tag_id}

Tag assignments (per-entity-row)
    POST   /api/tags/assign
    POST   /api/tags/unassign
    GET    /api/tags/for?entity_type=...&entity_id=...

All endpoints are tenant-scoped. Assignments refuse to touch rows
that do not belong to the caller's org — via the shared
``_assert_entity_belongs`` guard pattern introduced in Item 59.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.inventory import Product
from app.models.invoicing import Customer, Invoice
from app.models.tag import Tag, TagAssignment
from app.services import tag as svc
from app.services.audit import log_action
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/tags", tags=["tags"], dependencies=[Depends(require_module("inventory"))])

log = logging.getLogger(__name__)


class TagCreate(BaseModel):
    name:  str
    color: str | None = None


class TagOut(BaseModel):
    id:         uuid.UUID
    name:       str
    slug:       str
    color:      str | None
    created_at: datetime


class AssignRequest(BaseModel):
    tag_id:      uuid.UUID
    entity_type: str
    entity_id:   uuid.UUID


class AssignmentOut(BaseModel):
    id:          uuid.UUID
    tag_id:      uuid.UUID
    entity_type: str
    entity_id:   uuid.UUID
    created_at:  datetime


def _entity_model(entity_type: str):
    return {
        "product": Product,
        "customer": Customer,
        "invoice": Invoice,
    }.get(entity_type)


async def _assert_entity_belongs(
    db: AsyncSession,
    org_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
) -> None:
    try:
        svc.validate_entity_type(entity_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    Model = _entity_model(entity_type)
    row = await db.get(Model, entity_id)
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail=f"{entity_type} not found")


# ── Tag catalogue ─────────────────────────────────────────────────────────


@router.post("", response_model=TagOut, status_code=status.HTTP_201_CREATED)
async def create_tag(
    body: TagCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    name = svc.normalise_name(body.name)
    try:
        svc.validate_name(name)
        slug = svc.slugify(name)
        color = svc.validate_color(body.color)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    dup = (
        await db.scalars(
            select(Tag).where(
                Tag.org_id == member.org_id, Tag.slug == slug
            )
        )
    ).first()
    if dup is not None:
        raise HTTPException(status_code=409, detail="slug already exists")

    row = Tag(org_id=member.org_id, name=name, slug=slug, color=color)
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="tag.created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="tag",
        target_id=str(row.id),
        ip_address=request.client.host if request.client else None,
        extra={"slug": slug},
    )
    await db.commit()
    await db.refresh(row)
    return row


@router.get("", response_model=list[TagOut])
async def list_tags(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    rows = (
        await db.scalars(
            select(Tag)
            .where(Tag.org_id == member.org_id)
            .order_by(Tag.name.asc())
        )
    ).all()
    return list(rows)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await db.get(Tag, tag_id)
    if row is None or row.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="Tag not found")
    slug = row.slug
    await db.delete(row)
    await log_action(
        db,
        action="tag.deleted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="tag",
        target_id=str(tag_id),
        ip_address=request.client.host if request.client else None,
        extra={"slug": slug},
    )
    await db.commit()
    return None


# ── Assignments ───────────────────────────────────────────────────────────


@router.post(
    "/assign",
    response_model=AssignmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def assign_tag(
    body: AssignRequest,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx

    tag = await db.get(Tag, body.tag_id)
    if tag is None or tag.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="Tag not found")

    await _assert_entity_belongs(
        db, member.org_id, body.entity_type, body.entity_id
    )

    # Idempotent — return the existing assignment if the pair is
    # already linked, rather than 409. Callers commonly re-POST when
    # toggling UI state.
    existing = (
        await db.scalars(
            select(TagAssignment).where(
                TagAssignment.tag_id == body.tag_id,
                TagAssignment.entity_type == body.entity_type,
                TagAssignment.entity_id == body.entity_id,
            )
        )
    ).first()
    if existing is not None:
        return existing

    row = TagAssignment(
        org_id=member.org_id,
        tag_id=body.tag_id,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
    )
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="tag.assigned",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="tag_assignment",
        target_id=str(row.id),
        ip_address=request.client.host if request.client else None,
        extra={
            "tag_id": str(body.tag_id),
            "entity_type": body.entity_type,
            "entity_id": str(body.entity_id),
        },
    )
    await db.commit()
    await db.refresh(row)
    return row


@router.post("/unassign", status_code=status.HTTP_204_NO_CONTENT)
async def unassign_tag(
    body: AssignRequest,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    tag = await db.get(Tag, body.tag_id)
    if tag is None or tag.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="Tag not found")

    row = (
        await db.scalars(
            select(TagAssignment).where(
                TagAssignment.tag_id == body.tag_id,
                TagAssignment.entity_type == body.entity_type,
                TagAssignment.entity_id == body.entity_id,
                TagAssignment.org_id == member.org_id,
            )
        )
    ).first()
    if row is None:
        # Idempotent unassign — no row is the success case.
        return None

    await db.delete(row)
    await log_action(
        db,
        action="tag.unassigned",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="tag_assignment",
        target_id=str(row.id),
        ip_address=request.client.host if request.client else None,
        extra={
            "tag_id": str(body.tag_id),
            "entity_type": body.entity_type,
            "entity_id": str(body.entity_id),
        },
    )
    await db.commit()
    return None


@router.get("/for", response_model=list[TagOut])
async def list_tags_for_entity(
    entity_type: str = Query(...),
    entity_id:   uuid.UUID = Query(...),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    await _assert_entity_belongs(db, member.org_id, entity_type, entity_id)

    rows = (
        await db.execute(
            select(Tag)
            .join(TagAssignment, TagAssignment.tag_id == Tag.id)
            .where(
                TagAssignment.org_id == member.org_id,
                TagAssignment.entity_type == entity_type,
                TagAssignment.entity_id == entity_id,
            )
            .order_by(Tag.name.asc())
        )
    ).all()
    return [r[0] for r in rows]
