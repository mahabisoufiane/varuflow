"""Sentiment analysis router (Sprint 12) — prefix /api/inbox/sentiment."""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.sentiment_log import ConversationSentimentLog
from app.models.unified_message import UnifiedInboxThread, UnifiedMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/inbox/sentiment", tags=["sentiment-analysis"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class SentimentAnalyzeIn(BaseModel):
    message_id: uuid.UUID


class SentimentAnalyzeOut(BaseModel):
    sentiment: str
    confidence: Optional[float]
    flagged: bool


class SentimentLogOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    thread_id: uuid.UUID
    message_id: Optional[uuid.UUID]
    sentiment: str
    confidence: Optional[float]
    flagged_for_manager: bool
    created_at: datetime

    class Config:
        from_attributes = True


class FlaggedThreadOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: Optional[uuid.UUID]
    channel: str
    subject: Optional[str]
    last_message_at: datetime
    sentiment: Optional[str]
    is_archived: bool
    is_read: bool

    class Config:
        from_attributes = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/analyze", response_model=SentimentAnalyzeOut, status_code=201)
async def analyze_sentiment(
    body: SentimentAnalyzeIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        msg = await db.get(UnifiedMessage, body.message_id)
        if not msg or msg.org_id != org_id:
            raise HTTPException(status_code=404, detail="Message not found")

        sentiment = "neutral"
        confidence = None
        flagged = False

        try:
            import openai
            client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Classify the sentiment of the following message as "
                            "positive, neutral, or negative. "
                            'Return JSON: {"sentiment": "positive|neutral|negative", "confidence": 0.0-1.0}. '
                            "Return only the JSON."
                        ),
                    },
                    {"role": "user", "content": msg.body},
                ],
                max_tokens=100,
                temperature=0.1,
            )
            import json
            parsed = json.loads(response.choices[0].message.content.strip())
            sentiment = parsed.get("sentiment", "neutral")
            confidence = float(parsed.get("confidence", 0.0))
        except Exception as ai_err:
            logger.error(
                f"OpenAI sentiment failed: {ai_err}",
                extra={"org_id": str(org_id), "message_id": str(body.message_id)},
            )

        flagged = sentiment == "negative"

        log = ConversationSentimentLog(
            org_id=org_id,
            thread_id=msg.thread_id,
            message_id=body.message_id,
            sentiment=sentiment,
            confidence=confidence,
            flagged_for_manager=flagged,
        )
        db.add(log)

        # Update thread sentiment
        thread = await db.get(UnifiedInboxThread, msg.thread_id)
        if thread and thread.org_id == org_id:
            thread.sentiment = sentiment
            thread.updated_at = datetime.now(timezone.utc)

        await db.commit()
        return SentimentAnalyzeOut(sentiment=sentiment, confidence=confidence, flagged=flagged)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"analyze_sentiment failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/flagged", response_model=list[FlaggedThreadOut])
async def get_flagged_threads(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
):
    try:
        org_id = _org_id(ctx)
        # Find thread IDs with flagged sentiment logs
        flagged_q = (
            select(ConversationSentimentLog.thread_id)
            .where(
                ConversationSentimentLog.org_id == org_id,
                ConversationSentimentLog.flagged_for_manager.is_(True),
            )
            .distinct()
        )
        flagged_thread_ids = list((await db.execute(flagged_q)).scalars().all())

        q = (
            select(UnifiedInboxThread)
            .where(
                UnifiedInboxThread.org_id == org_id,
                UnifiedInboxThread.id.in_(flagged_thread_ids)
                | (UnifiedInboxThread.sentiment == "negative"),
            )
            .order_by(UnifiedInboxThread.last_message_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await db.execute(q)).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_flagged_threads failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
