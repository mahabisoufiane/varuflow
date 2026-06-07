"""Message translation router (Sprint 12) — prefix /api/inbox/translate."""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.message_translation import MessageTranslation
from app.models.unified_message import UnifiedMessage
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/inbox/translate", tags=["message-translation"], dependencies=[Depends(require_module("crm"))])


# ── Schemas ──────────────────────────────────────────────────────────────────

class TranslateIn(BaseModel):
    message_id: uuid.UUID
    target_language: str = Field(..., max_length=5)


class TranslationOut(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    source_language: str
    target_language: str
    translated_body: str
    translated_by: str
    created_at: datetime
    error: Optional[str] = None

    class Config:
        from_attributes = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=TranslationOut, status_code=201)
async def translate_message(
    body: TranslateIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        msg = await db.get(UnifiedMessage, body.message_id)
        if not msg or msg.org_id != org_id:
            raise HTTPException(status_code=404, detail="Message not found")

        # Check if translation already exists (uq constraint)
        existing_q = select(MessageTranslation).where(
            MessageTranslation.message_id == body.message_id,
            MessageTranslation.target_language == body.target_language,
        )
        existing = (await db.execute(existing_q)).scalar_one_or_none()
        if existing:
            return existing

        # Call OpenAI to translate
        translated_body = msg.body
        translated_by = "openai"
        error_field = None
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"You are a professional translator. Translate the following text "
                            f"to {body.target_language}. Return only the translated text."
                        ),
                    },
                    {"role": "user", "content": msg.body},
                ],
                max_tokens=2000,
                temperature=0.2,
            )
            translated_body = response.choices[0].message.content.strip()
        except Exception as ai_err:
            logger.error(
                f"OpenAI translation failed: {ai_err}",
                extra={"org_id": str(org_id), "message_id": str(body.message_id)},
            )
            translated_by = "fallback"
            error_field = "translation_unavailable"

        record = MessageTranslation(
            org_id=org_id,
            message_id=body.message_id,
            source_language="auto",
            target_language=body.target_language,
            translated_body=translated_body,
            translated_by=translated_by,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)

        out = TranslationOut.model_validate(record)
        out.error = error_field
        return out
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"translate_message failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{message_id}", response_model=list[TranslationOut])
async def get_message_translations(
    message_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        q = select(MessageTranslation).where(
            MessageTranslation.message_id == message_id,
            MessageTranslation.org_id == org_id,
        )
        rows = (await db.execute(q)).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_message_translations failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
