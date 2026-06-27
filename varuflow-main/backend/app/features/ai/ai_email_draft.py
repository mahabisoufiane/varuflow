"""AI email draft router — Sprint 13.  prefix /api/ai/email-drafts"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.features.ai.model_ai_email_draft import AiEmailDraft
from app.features.notifications.unified_message import UnifiedMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai/email-drafts", tags=["ai-email-drafts"], dependencies=[Depends(require_module("ai"))])


def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Schemas ────────────────────────────────────────────────────────────────────

class GenerateEmailDraftIn(BaseModel):
    message_id: uuid.UUID
    thread_id: Optional[uuid.UUID] = None
    tone: Optional[str] = None


class AiEmailDraftOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    message_id: Optional[uuid.UUID]
    thread_id: Optional[uuid.UUID]
    draft_text: str
    model_used: str
    tone: Optional[str]
    accepted: Optional[bool]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=AiEmailDraftOut, status_code=201)
async def generate_email_draft(
    body: GenerateEmailDraftIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        msg = await db.get(UnifiedMessage, body.message_id)
        if not msg or msg.org_id != org_id:
            raise HTTPException(status_code=404, detail="Message not found")

        tone_hint = f" Use a {body.tone} tone." if body.tone else ""
        prompt = (
            f"Write a reply in the merchant's voice to the following message:{tone_hint}\n\n"
            f"{msg.body}"
        )

        draft_text = "Thank you for your message. We will get back to you shortly."
        model_used = "gpt-4o"

        try:
            import openai
            client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
            )
            draft_text = response.choices[0].message.content.strip()
        except Exception as ai_err:
            logger.error(
                f"OpenAI call failed in generate_email_draft: {str(ai_err)}",
                extra={"org_id": str(org_id)},
            )

        record = AiEmailDraft(
            org_id=org_id,
            message_id=body.message_id,
            thread_id=body.thread_id,
            prompt_context={"tone": body.tone},
            draft_text=draft_text,
            model_used=model_used,
            tone=body.tone,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"generate_email_draft failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=list[AiEmailDraftOut])
async def list_email_drafts(
    message_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        q = select(AiEmailDraft).where(AiEmailDraft.org_id == org_id)
        if message_id:
            q = q.where(AiEmailDraft.message_id == message_id)
        q = q.order_by(AiEmailDraft.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(q)
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_email_drafts failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{draft_id}/accept", response_model=AiEmailDraftOut)
async def accept_email_draft(
    draft_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(AiEmailDraft, draft_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="AI email draft not found")
        record.accepted = True
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"accept_email_draft failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{draft_id}/reject", response_model=AiEmailDraftOut)
async def reject_email_draft(
    draft_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(AiEmailDraft, draft_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="AI email draft not found")
        record.accepted = False
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"reject_email_draft failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
