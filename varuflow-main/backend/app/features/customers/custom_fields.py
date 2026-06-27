"""Custom fields router (Item 59).

Endpoints
---------

Definitions (per-org schema)
    POST   /api/custom-fields/definitions
    GET    /api/custom-fields/definitions?entity_type=...
    DELETE /api/custom-fields/definitions/{id}

Values (per-entity-row payload)
    PUT    /api/custom-fields/values
    GET    /api/custom-fields/values?entity_type=...&entity_id=...

All endpoints require an authenticated org member. Every query is
filtered on ``member.org_id`` and the entity row it refers to is
asserted to live inside the caller's org before any write.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from .custom_field import CustomFieldDefinition, CustomFieldValue
from app.features.inventory.models import Product
from app.features.invoicing.models import Customer, Invoice
from app.services import custom_field as svc
from app.services.audit import log_action
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/custom-fields", tags=["custom-fields"], dependencies=[Depends(require_module("inventory"))])

log = logging.getLogger(__name__)


class DefinitionCreate(BaseModel):
    entity_type: str
    name:        str
    label:       str
    field_type:  str
    is_required: bool = False
    options:     list[str] | None = None
    display_order: int = 0


class DefinitionOut(BaseModel):
    id:            uuid.UUID
    entity_type:   str
    name:          str
    label:         str
    field_type:    str
    is_required:   bool
    options:       list[str] | None
    display_order: int
    created_at:    datetime


class ValueUpsert(BaseModel):
    entity_type:   str
    entity_id:     uuid.UUID
    definition_id: uuid.UUID
    value:         str | int | float | bool | None = None


class ValueOut(BaseModel):
    id:            uuid.UUID
    entity_type:   str
    entity_id:     uuid.UUID
    definition_id: uuid.UUID
    field_type:    str
    name:          str
    label:         str
    raw:           str | None
    cast:          object | None
    updated_at:    datetime


def _entity_model(entity_type: str):
    return {
        "product": Product,
        "customer": Customer,
        "invoice": Invoice,
    }.get(entity_type)


async def _assert_entity_belongs(
    db: AsyncSession, org_id: uuid.UUID, entity_type: str, entity_id: uuid.UUID,
) -> None:
    Model = _entity_model(entity_type)
    if Model is None:
        raise HTTPException(status_code=400, detail="Unknown entity_type")
    row = await db.get(Model, entity_id)
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail=f"{entity_type} not found")


# ── Definitions ────────────────────────────────────────────────────────────


@router.post(
    "/definitions",
    response_model=DefinitionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_definition(
    body: DefinitionCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    name = svc.normalise_name(body.name)
    try:
        svc.validate_definition(
            svc.DefinitionInput(
                entity_type=body.entity_type,
                name=name,
                label=body.label.strip() if body.label else "",
                field_type=body.field_type,
                is_required=body.is_required,
                options=body.options,
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Reject duplicate names within the same (org, entity_type)
    dup = (
        await db.scalars(
            select(CustomFieldDefinition).where(
                CustomFieldDefinition.org_id == member.org_id,
                CustomFieldDefinition.entity_type == body.entity_type,
                CustomFieldDefinition.name == name,
            )
        )
    ).first()
    if dup is not None:
        raise HTTPException(status_code=409, detail="name already exists")

    row = CustomFieldDefinition(
        org_id=member.org_id,
        entity_type=body.entity_type,
        name=name,
        label=body.label.strip(),
        field_type=body.field_type,
        is_required=body.is_required,
        options=body.options if body.field_type == "select" else None,
        display_order=body.display_order,
    )
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="custom_field.definition_created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="custom_field_definition",
        target_id=str(row.id),
        ip_address=request.client.host if request.client else None,
        extra={"entity_type": body.entity_type, "name": name},
    )
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/definitions", response_model=list[DefinitionOut])
async def list_definitions(
    entity_type: str | None = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    stmt = (
        select(CustomFieldDefinition)
        .where(CustomFieldDefinition.org_id == member.org_id)
        .order_by(
            CustomFieldDefinition.entity_type.asc(),
            CustomFieldDefinition.display_order.asc(),
            CustomFieldDefinition.name.asc(),
        )
    )
    if entity_type:
        if entity_type not in svc.ALLOWED_ENTITY_TYPES:
            raise HTTPException(status_code=400, detail="Unknown entity_type")
        stmt = stmt.where(CustomFieldDefinition.entity_type == entity_type)
    rows = (await db.scalars(stmt)).all()
    return list(rows)


@router.delete(
    "/definitions/{definition_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_definition(
    definition_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await db.get(CustomFieldDefinition, definition_id)
    if row is None or row.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="Definition not found")
    await db.delete(row)
    await log_action(
        db,
        action="custom_field.definition_deleted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="custom_field_definition",
        target_id=str(definition_id),
        ip_address=request.client.host if request.client else None,
        extra={"entity_type": row.entity_type, "name": row.name},
    )
    await db.commit()
    return None


# ── Values ─────────────────────────────────────────────────────────────────


@router.put("/values", response_model=ValueOut)
async def upsert_value(
    body: ValueUpsert,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx

    # 1. Definition must exist and belong to the caller's org.
    definition = await db.get(CustomFieldDefinition, body.definition_id)
    if definition is None or definition.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="Definition not found")
    # 2. entity_type on body must match the definition.
    if definition.entity_type != body.entity_type:
        raise HTTPException(
            status_code=400,
            detail="entity_type does not match definition",
        )
    # 3. Entity row must live in the caller's org.
    await _assert_entity_belongs(
        db, member.org_id, body.entity_type, body.entity_id
    )
    # 4. Coerce + validate value per the definition's type rules.
    try:
        canonical = svc.coerce_value(
            definition.field_type,
            body.value,
            options=definition.options,
            required=definition.is_required,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 5. Upsert via (definition_id, entity_id).
    existing = (
        await db.scalars(
            select(CustomFieldValue).where(
                CustomFieldValue.definition_id == body.definition_id,
                CustomFieldValue.entity_id == body.entity_id,
            )
        )
    ).first()
    now = datetime.now(timezone.utc)
    if existing is None:
        row = CustomFieldValue(
            org_id=member.org_id,
            definition_id=body.definition_id,
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            value=canonical,
            updated_at=now,
        )
        db.add(row)
        await db.flush()
    else:
        existing.value = canonical
        existing.updated_at = now
        row = existing

    await log_action(
        db,
        action="custom_field.value_upserted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="custom_field_value",
        target_id=str(row.id),
        ip_address=request.client.host if request.client else None,
        extra={
            "entity_type": body.entity_type,
            "entity_id": str(body.entity_id),
            "definition_id": str(body.definition_id),
        },
    )
    await db.commit()
    await db.refresh(row)

    return ValueOut(
        id=row.id,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        definition_id=row.definition_id,
        field_type=definition.field_type,
        name=definition.name,
        label=definition.label,
        raw=row.value,
        cast=svc.cast_for_read(definition.field_type, row.value),
        updated_at=row.updated_at,
    )


@router.get("/values", response_model=list[ValueOut])
async def list_values(
    entity_type: str = Query(...),
    entity_id:   uuid.UUID = Query(...),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    if entity_type not in svc.ALLOWED_ENTITY_TYPES:
        raise HTTPException(status_code=400, detail="Unknown entity_type")
    await _assert_entity_belongs(db, member.org_id, entity_type, entity_id)

    rows = (
        await db.execute(
            select(CustomFieldValue, CustomFieldDefinition)
            .join(
                CustomFieldDefinition,
                CustomFieldDefinition.id == CustomFieldValue.definition_id,
            )
            .where(
                CustomFieldValue.org_id == member.org_id,
                CustomFieldValue.entity_type == entity_type,
                CustomFieldValue.entity_id == entity_id,
            )
            .order_by(
                CustomFieldDefinition.display_order.asc(),
                CustomFieldDefinition.name.asc(),
            )
        )
    ).all()

    return [
        ValueOut(
            id=v.id,
            entity_type=v.entity_type,
            entity_id=v.entity_id,
            definition_id=v.definition_id,
            field_type=d.field_type,
            name=d.name,
            label=d.label,
            raw=v.value,
            cast=svc.cast_for_read(d.field_type, v.value),
            updated_at=v.updated_at,
        )
        for v, d in rows
    ]
