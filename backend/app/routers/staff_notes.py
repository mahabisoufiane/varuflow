"""Staff Notes router — Sprint 9: Personalization.

Endpoint map
------------
    GET    /api/staff-notes                 — list for customer
    POST   /api/staff-notes                 — create
    PATCH  /api/staff-notes/{id}            — update
    DELETE /api/staff-notes/{id}            — delete
    POST   /api/staff-notes/{id}/confirm    — customer confirms note
"""
from __future__ import annotations

import logging
import uuid
import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.customer_staff_note import CustomerStaffNote
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/staff-notes", tags=["staff-notes"], dependencies=[Depends(require_module("hr"))])


class StaffNoteIn(BaseModel):
    customer_id: uuid.UUID
    staff_user_id: uuid.UUID | None = None
    note_text: str
    is_visible_to_customer: bool = False


class StaffNotePatch(BaseModel):
    note_text: str | None = None
    is_visible_to_customer: bool | None = None


class StaffNoteOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    staff_user_id: uuid.UUID | None
    note_text: str
    is_visible_to_customer: bool
    confirmed_by_customer_at: datetime.datetime | None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[StaffNoteOut])
async def list_staff_notes(
    customer_id: uuid.UUID = Query(...),
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        result = await db.execute(
            select(CustomerStaffNote).where(
                CustomerStaffNote.org_id == org_id,
                CustomerStaffNote.customer_id == customer_id,
            ).order_by(CustomerStaffNote.created_at.desc())
        )
        return [StaffNoteOut.model_validate(r) for r in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_staff_notes failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=StaffNoteOut, status_code=201)
async def create_staff_note(
    body: StaffNoteIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        row = CustomerStaffNote(
            org_id=org_id,
            customer_id=body.customer_id,
            staff_user_id=body.staff_user_id,
            note_text=body.note_text,
            is_visible_to_customer=body.is_visible_to_customer,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return StaffNoteOut.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_staff_note failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


async def _get_note(note_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession) -> CustomerStaffNote:
    result = await db.execute(
        select(CustomerStaffNote).where(
            CustomerStaffNote.id == note_id,
            CustomerStaffNote.org_id == org_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Staff note not found")
    return row


@router.patch("/{note_id}", response_model=StaffNoteOut)
async def update_staff_note(
    note_id: uuid.UUID,
    body: StaffNotePatch,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        row = await _get_note(note_id, org_id, db)
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        row.updated_at = datetime.datetime.utcnow()
        await db.commit()
        await db.refresh(row)
        return StaffNoteOut.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_staff_note failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{note_id}", status_code=204)
async def delete_staff_note(
    note_id: uuid.UUID,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        row = await _get_note(note_id, org_id, db)
        await db.delete(row)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_staff_note failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{note_id}/confirm", response_model=StaffNoteOut)
async def confirm_staff_note(
    note_id: uuid.UUID,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Portal action: customer confirms they have seen the note."""
    try:
        org_id = member["org_id"]
        row = await _get_note(note_id, org_id, db)
        row.confirmed_by_customer_at = datetime.datetime.utcnow()
        row.updated_at = datetime.datetime.utcnow()
        await db.commit()
        await db.refresh(row)
        return StaffNoteOut.model_validate(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"confirm_staff_note failed: {str(e)}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")
