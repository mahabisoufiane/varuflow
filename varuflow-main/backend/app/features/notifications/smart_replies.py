"""Smart replies router (Sprint 12) — prefix /api/inbox/smart-reply."""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from .smart_reply_log import SmartReplyLog
from .unified_message import UnifiedInboxThread, UnifiedMessage
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/inbox/smart-reply", tags=["smart-replies"], dependencies=[Depends(require_module("ai"))])


# ── Schemas ──────────────────────────────────────────────────────────────────

class SmartReplyRequestIn(BaseModel):
    message_id: uuid.UUID


class SmartReplySuggestion(BaseModel):
    text: str
    tone: str


class SmartReplyOut(BaseModel):
    suggestions: list[SmartReplySuggestion]
    log_id: uuid.UUID


class AcceptSuggestionIn(BaseModel):
    index: int = Field(..., ge=0, le=2)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=SmartReplyOut, status_code=201)
async def generate_smart_replies(
    body: SmartReplyRequestIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        msg = await db.get(UnifiedMessage, body.message_id)
        if not msg or msg.org_id != org_id:
            raise HTTPException(status_code=404, detail="Message not found")

        thread = await db.get(UnifiedInboxThread, msg.thread_id)
        subject = thread.subject if thread else ""

        fallback_suggestions = [
            {"text": "Thank you for reaching out. We'll look into this.", "tone": "professional"},
            {"text": "Hi! Thanks for your message — we're on it!", "tone": "friendly"},
            {"text": "Got it. Will respond shortly.", "tone": "brief"},
        ]
        suggestions = fallback_suggestions

        try:
            import openai
            client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            prompt = (
                f"Subject: {subject}\n\nMessage: {msg.body}\n\n"
                "Generate 3 reply suggestions with different tones: professional, friendly, and brief. "
                'Return JSON array: [{"text": "...", "tone": "professional"}, {"text": "...", "tone": "friendly"}, {"text": "...", "tone": "brief"}]. '
                "Return only the JSON array, no other text."
            )
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful customer service assistant."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=600,
                temperature=0.7,
            )
            import json
            content = response.choices[0].message.content.strip()
            parsed = json.loads(content)
            if isinstance(parsed, list) and len(parsed) == 3:
                suggestions = parsed
        except Exception as ai_err:
            logger.error(
                f"OpenAI smart reply failed: {ai_err}",
                extra={"org_id": str(org_id), "message_id": str(body.message_id)},
            )

        log = SmartReplyLog(
            org_id=org_id,
            message_id=body.message_id,
            suggestions=suggestions,
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)

        return SmartReplyOut(
            suggestions=[SmartReplySuggestion(**s) for s in suggestions],
            log_id=log.id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"generate_smart_replies failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{log_id}/accept")
async def accept_suggestion(
    log_id: uuid.UUID,
    body: AcceptSuggestionIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        log = await db.get(SmartReplyLog, log_id)
        if not log or log.org_id != org_id:
            raise HTTPException(status_code=404, detail="Smart reply log not found")
        log.accepted_index = body.index
        await db.commit()
        return {"accepted_index": body.index}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"accept_suggestion failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
