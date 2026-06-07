"""Saved filters router (Item 61).

Endpoints
---------

    POST   /api/saved-filters
    GET    /api/saved-filters?entity_type=...
    PATCH  /api/saved-filters/{id}
    DELETE /api/saved-filters/{id}

Listing returns:
    - all rows owned by the caller for the given entity_type
    - plus every ``is_shared=true`` row in the same org

Edit rules:
    - row owner can always patch / delete
    - an org OWNER can patch / delete any row (including shared ones
      from other users)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.organization import OrgRole
from app.models.saved_filter import SavedFilter
from app.services import saved_filter as svc
from app.services.audit import log_action
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/saved-filters", tags=["saved-filters"], dependencies=[Depends(require_module("settings"))])

log = logging.getLogger(__name__)


class FilterCreate(BaseModel):
    entity_type: str
    name:        str
    definition:  dict
    is_shared:   bool = False


class FilterUpdate(BaseModel):
    name:       str | None = None
    definition: dict | None = None
    is_shared:  bool | None = None


class FilterOut(BaseModel):
    id:          uuid.UUID
    user_id:     uuid.UUID
    entity_type: str
    name:        str
    definition:  dict
    is_shared:   bool
    created_at:  datetime
    updated_at:  datetime


def _is_owner(member) -> bool:
    return member.role == OrgRole.OWNER


@router.post("", response_model=FilterOut, status_code=status.HTTP_201_CREATED)
async def create_saved_filter(
    body: FilterCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    try:
        svc.validate_entity_type(body.entity_type)
        name = svc.validate_name(body.name)
        definition = svc.validate_definition(body.definition)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    dup = (
        await db.scalars(
            select(SavedFilter).where(
                SavedFilter.org_id == member.org_id,
                SavedFilter.user_id == user["user_id"],
                SavedFilter.entity_type == body.entity_type,
                SavedFilter.name == name,
            )
        )
    ).first()
    if dup is not None:
        raise HTTPException(status_code=409, detail="name already exists")

    row = SavedFilter(
        org_id=member.org_id,
        user_id=user["user_id"],
        entity_type=body.entity_type,
        name=name,
        definition=definition,
        is_shared=body.is_shared,
    )
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="saved_filter.created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="saved_filter",
        target_id=str(row.id),
        ip_address=request.client.host if request.client else None,
        extra={"entity_type": body.entity_type, "is_shared": body.is_shared},
    )
    await db.commit()
    await db.refresh(row)
    return row


@router.get("", response_model=list[FilterOut])
async def list_saved_filters(
    entity_type: str = Query(...),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    try:
        svc.validate_entity_type(entity_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    rows = (
        await db.scalars(
            select(SavedFilter)
            .where(
                SavedFilter.org_id == member.org_id,
                SavedFilter.entity_type == entity_type,
                or_(
                    SavedFilter.user_id == user["user_id"],
                    SavedFilter.is_shared.is_(True),
                ),
            )
            .order_by(SavedFilter.name.asc())
        )
    ).all()
    return list(rows)


@router.patch("/{filter_id}", response_model=FilterOut)
async def update_saved_filter(
    filter_id: uuid.UUID,
    body: FilterUpdate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await db.get(SavedFilter, filter_id)
    if row is None or row.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="Filter not found")
    if not svc.can_edit(
        row.user_id, user["user_id"], _is_owner(member)
    ):
        raise HTTPException(status_code=403, detail="Not allowed")

    changed: list[str] = []
    try:
        if body.name is not None:
            new_name = svc.validate_name(body.name)
            if new_name != row.name:
                row.name = new_name
                changed.append("name")
        if body.definition is not None:
            row.definition = svc.validate_definition(body.definition)
            changed.append("definition")
        if body.is_shared is not None and body.is_shared != row.is_shared:
            row.is_shared = body.is_shared
            changed.append("is_shared")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if changed:
        row.updated_at = datetime.now(timezone.utc)
        await log_action(
            db,
            action="saved_filter.updated",
            org_id=member.org_id,
            actor_user_id=user["user_id"],
            target_type="saved_filter",
            target_id=str(row.id),
            ip_address=request.client.host if request.client else None,
            extra={"fields": changed},
        )
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/{filter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_filter(
    filter_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await db.get(SavedFilter, filter_id)
    if row is None or row.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="Filter not found")
    if not svc.can_edit(
        row.user_id, user["user_id"], _is_owner(member)
    ):
        raise HTTPException(status_code=403, detail="Not allowed")

    await db.delete(row)
    await log_action(
        db,
        action="saved_filter.deleted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="saved_filter",
        target_id=str(filter_id),
        ip_address=request.client.host if request.client else None,
        extra={"entity_type": row.entity_type},
    )
    await db.commit()
    return None
