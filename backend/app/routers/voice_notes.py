"""Customer voice notes (audio messages).

Endpoints
─────────
GET    /api/voice-notes                    → list voice notes for org
POST   /api/voice-notes                    → create voice note
GET    /api/voice-notes/{id}               → detail
PATCH  /api/voice-notes/{id}/read          → mark is_read=True
PATCH  /api/voice-notes/{id}/transcribe    → update transcription
DELETE /api/voice-notes/{id}               → delete
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.customer_voice_note import CustomerVoiceNote

router = APIRouter(prefix="/api/voice-notes", tags=["voice-notes"])
log = logging.getLogger(__name__)

_VALID_SENDER_TYPES = {"customer", "staff"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    user, _ = ctx
    return uuid.UUID(str(user["user_id"]))


def _note_out(note: CustomerVoiceNote) -> dict[str, Any]:
    return {
        "id": str(note.id),
        "org_id": str(note.org_id),
        "thread_id": str(note.thread_id) if note.thread_id else None,
        "sender_type": note.sender_type,
        "sender_id": str(note.sender_id) if note.sender_id else None,
        "customer_id": str(note.customer_id) if note.customer_id else None,
        "appointment_id": str(note.appointment_id) if note.appointment_id else None,
        "audio_url": note.audio_url,
        "duration_seconds": note.duration_seconds,
        "transcription": note.transcription,
        "is_read": note.is_read,
        "created_at": note.created_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class VoiceNoteIn(BaseModel):
    thread_id: Optional[uuid.UUID] = None
    sender_type: str = Field(min_length=1, max_length=10)
    audio_url: str = Field(min_length=1)
    duration_seconds: Optional[int] = None
    customer_id: Optional[uuid.UUID] = None
    appointment_id: Optional[uuid.UUID] = None


class TranscribeIn(BaseModel):
    transcription: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_voice_notes(
    thread_id: Optional[uuid.UUID] = Query(default=None),
    is_read: Optional[bool] = Query(default=None),
    sender_type: Optional[str] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        q = select(CustomerVoiceNote).where(CustomerVoiceNote.org_id == org_id)
        if thread_id is not None:
            q = q.where(CustomerVoiceNote.thread_id == thread_id)
        if is_read is not None:
            q = q.where(CustomerVoiceNote.is_read == is_read)
        if sender_type is not None:
            q = q.where(CustomerVoiceNote.sender_type == sender_type)
        q = q.order_by(CustomerVoiceNote.created_at.desc())
        notes = (await db.execute(q)).scalars().all()
        return [_note_out(n) for n in notes]
    except Exception as e:
        log.error("list_voice_notes failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_voice_note(
    body: VoiceNoteIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    try:
        if body.sender_type not in _VALID_SENDER_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"sender_type must be one of {_VALID_SENDER_TYPES}",
            )

        note = CustomerVoiceNote(
            org_id=org_id,
            thread_id=body.thread_id,
            sender_type=body.sender_type,
            sender_id=user_id,
            customer_id=body.customer_id,
            appointment_id=body.appointment_id,
            audio_url=body.audio_url,
            duration_seconds=body.duration_seconds,
        )
        db.add(note)
        await db.commit()
        await db.refresh(note)
        return _note_out(note)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_voice_note failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{note_id}")
async def get_voice_note(
    note_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        note = await db.scalar(
            select(CustomerVoiceNote).where(
                CustomerVoiceNote.id == note_id,
                CustomerVoiceNote.org_id == org_id,
            )
        )
        if not note:
            raise HTTPException(status_code=404, detail="Voice note not found")
        return _note_out(note)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_voice_note failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{note_id}/read")
async def mark_voice_note_read(
    note_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        note = await db.scalar(
            select(CustomerVoiceNote).where(
                CustomerVoiceNote.id == note_id,
                CustomerVoiceNote.org_id == org_id,
            )
        )
        if not note:
            raise HTTPException(status_code=404, detail="Voice note not found")
        note.is_read = True
        await db.commit()
        await db.refresh(note)
        return _note_out(note)
    except HTTPException:
        raise
    except Exception as e:
        log.error("mark_voice_note_read failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{note_id}/transcribe")
async def transcribe_voice_note(
    note_id: uuid.UUID,
    body: TranscribeIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        note = await db.scalar(
            select(CustomerVoiceNote).where(
                CustomerVoiceNote.id == note_id,
                CustomerVoiceNote.org_id == org_id,
            )
        )
        if not note:
            raise HTTPException(status_code=404, detail="Voice note not found")
        note.transcription = body.transcription
        await db.commit()
        await db.refresh(note)
        return _note_out(note)
    except HTTPException:
        raise
    except Exception as e:
        log.error("transcribe_voice_note failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{note_id}", status_code=204)
async def delete_voice_note(
    note_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        note = await db.scalar(
            select(CustomerVoiceNote).where(
                CustomerVoiceNote.id == note_id,
                CustomerVoiceNote.org_id == org_id,
            )
        )
        if not note:
            raise HTTPException(status_code=404, detail="Voice note not found")
        await db.delete(note)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_voice_note failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
