"""Voice notes — attach audio recordings to customers, suppliers, route stops, invoices

Audio files are stored in Supabase Storage. The frontend uploads directly to Supabase
and passes the resulting file_url to this endpoint for indexing.

Endpoints:
  POST /api/mobile/voice-notes
  GET  /api/mobile/voice-notes
  GET  /api/mobile/voice-notes/{id}
  DELETE /api/mobile/voice-notes/{id}
  POST /api/mobile/voice-notes/{id}/transcribe   (Whisper transcription via OpenAI)
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.mobile_field import VoiceNote

router = APIRouter(prefix="/api/mobile/voice-notes", tags=["mobile_voice_notes"])
log = logging.getLogger(__name__)

ENTITY_TYPES = {"customer", "supplier", "route_stop", "invoice"}


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Schemas ───────────────────────────────────────────────────────────────────

class VoiceNoteIn(BaseModel):
    entity_type: str      # customer|supplier|route_stop|invoice
    entity_id: uuid.UUID
    file_url: str         # Supabase Storage URL (frontend uploaded directly)
    duration_seconds: Optional[int] = None

class VoiceNoteOut(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    file_url: str
    duration_seconds: Optional[int]
    transcription: Optional[str]
    created_at: str

class VoiceNotesOut(BaseModel):
    notes: list[VoiceNoteOut]
    total: int


def _out(v: VoiceNote) -> VoiceNoteOut:
    return VoiceNoteOut(
        id=str(v.id),
        entity_type=v.entity_type,
        entity_id=str(v.entity_id),
        file_url=v.file_url,
        duration_seconds=v.duration_seconds,
        transcription=v.transcription,
        created_at=v.created_at.isoformat(),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=VoiceNoteOut)
async def create_voice_note(
    body: VoiceNoteIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        if body.entity_type not in ENTITY_TYPES:
            raise HTTPException(status_code=422, detail=f"entity_type must be one of {ENTITY_TYPES}")
        if not body.file_url.strip():
            raise HTTPException(status_code=422, detail="file_url is required")

        _, member = ctx
        note = VoiceNote(
            org_id=org_id,
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            file_url=body.file_url,
            duration_seconds=body.duration_seconds,
            created_by=member.user_id if hasattr(member, "user_id") else None,
        )
        db.add(note)
        await db.commit()
        await db.refresh(note)
        return _out(note)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_voice_note failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=VoiceNotesOut)
async def list_voice_notes(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[uuid.UUID] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        q = select(VoiceNote).where(VoiceNote.org_id == org_id)
        if entity_type:
            q = q.where(VoiceNote.entity_type == entity_type)
        if entity_id:
            q = q.where(VoiceNote.entity_id == entity_id)

        count_row = await db.execute(
            select(func.count(VoiceNote.id)).where(VoiceNote.org_id == org_id)
        )
        total = count_row.scalar_one() or 0
        rows = await db.execute(q.order_by(VoiceNote.created_at.desc()).limit(limit).offset((page - 1) * limit))
        return VoiceNotesOut(notes=[_out(v) for v in rows.scalars()], total=total)
    except Exception as e:
        log.error("list_voice_notes failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{note_id}", response_model=VoiceNoteOut)
async def get_voice_note(
    note_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(VoiceNote).where(VoiceNote.id == note_id, VoiceNote.org_id == org_id)
        )
        note = row.scalar_one_or_none()
        if not note:
            raise HTTPException(status_code=404, detail="Voice note not found")
        return _out(note)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_voice_note failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{note_id}")
async def delete_voice_note(
    note_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(VoiceNote).where(VoiceNote.id == note_id, VoiceNote.org_id == org_id)
        )
        note = row.scalar_one_or_none()
        if not note:
            raise HTTPException(status_code=404, detail="Voice note not found")
        await db.delete(note)
        await db.commit()
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_voice_note failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{note_id}/transcribe", response_model=VoiceNoteOut)
async def transcribe_voice_note(
    note_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Transcribe audio via OpenAI Whisper API. Downloads file from Supabase Storage and posts to Whisper."""
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(VoiceNote).where(VoiceNote.id == note_id, VoiceNote.org_id == org_id)
        )
        note = row.scalar_one_or_none()
        if not note:
            raise HTTPException(status_code=404, detail="Voice note not found")

        openai_key = os.getenv("OPENAI_API_KEY", "")
        if not openai_key:
            raise HTTPException(status_code=503, detail="OpenAI not configured — transcription unavailable")

        # Download audio file
        async with httpx.AsyncClient(timeout=30) as client:
            audio_resp = await client.get(note.file_url)
        if audio_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to download voice note audio")

        # Determine filename/content type
        content_type = audio_resp.headers.get("content-type", "audio/webm")
        ext = "webm" if "webm" in content_type else "mp4" if "mp4" in content_type else "wav"
        filename = f"voice_{note.id}.{ext}"

        # Submit to Whisper
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                whisper_resp = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {openai_key}"},
                    files={"file": (filename, audio_resp.content, content_type)},
                    data={"model": "whisper-1"},
                )
            if whisper_resp.status_code == 200:
                transcription = whisper_resp.json().get("text", "")
                note.transcription = transcription
            else:
                log.error("whisper_api error: %s", whisper_resp.text)
                raise HTTPException(status_code=502, detail="Transcription failed — Whisper API error")
        except HTTPException:
            raise
        except Exception as ex:
            log.error("whisper_call failed: %s", str(ex))
            raise HTTPException(status_code=500, detail="Transcription service unavailable")

        await db.commit()
        await db.refresh(note)
        return _out(note)
    except HTTPException:
        raise
    except Exception as e:
        log.error("transcribe_voice_note failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
