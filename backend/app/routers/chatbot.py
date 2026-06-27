"""Chatbot router (Sprint 11) — prefix /api/chatbot."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.chatbot import ChatbotConfig, ChatbotConversation
from app.models.knowledge_base import KbArticle

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chatbot", tags=["chatbot"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ChatbotConfigOut(BaseModel):
    id: Optional[uuid.UUID]
    org_id: uuid.UUID
    is_enabled: bool
    welcome_message: Optional[str]
    escalation_threshold: int
    knowledge_base_enabled: bool
    handoff_email: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class UpsertConfigIn(BaseModel):
    is_enabled: bool = True
    welcome_message: Optional[str] = None
    escalation_threshold: int = Field(default=3, ge=1)
    knowledge_base_enabled: bool = True
    handoff_email: Optional[str] = Field(default=None, max_length=200)


class ChatbotConversationOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    visitor_id: uuid.UUID
    session_id: Optional[uuid.UUID]
    messages: list[Any]
    escalated_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatIn(BaseModel):
    visitor_id: uuid.UUID
    org_id: uuid.UUID
    message: str


class ChatOut(BaseModel):
    conversation_id: uuid.UUID
    reply: str
    escalated: bool


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/config", response_model=ChatbotConfigOut)
async def get_chatbot_config(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        config = (
            await db.execute(
                select(ChatbotConfig).where(ChatbotConfig.org_id == org_id)
            )
        ).scalars().first()
        if config is None:
            # Return default values without persisting
            return ChatbotConfigOut(
                id=None,
                org_id=org_id,
                is_enabled=True,
                welcome_message=None,
                escalation_threshold=3,
                knowledge_base_enabled=True,
                handoff_email=None,
                created_at=None,
                updated_at=None,
            )
        return config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_chatbot_config failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/config", response_model=ChatbotConfigOut)
async def upsert_chatbot_config(
    body: UpsertConfigIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        stmt = (
            pg_insert(ChatbotConfig)
            .values(
                org_id=org_id,
                is_enabled=body.is_enabled,
                welcome_message=body.welcome_message,
                escalation_threshold=body.escalation_threshold,
                knowledge_base_enabled=body.knowledge_base_enabled,
                handoff_email=body.handoff_email,
            )
            .on_conflict_do_update(
                constraint="uq_chatbot_configs_org",
                set_={
                    "is_enabled": body.is_enabled,
                    "welcome_message": body.welcome_message,
                    "escalation_threshold": body.escalation_threshold,
                    "knowledge_base_enabled": body.knowledge_base_enabled,
                    "handoff_email": body.handoff_email,
                    "updated_at": datetime.now(timezone.utc),
                },
            )
            .returning(ChatbotConfig)
        )
        result = await db.execute(stmt)
        await db.commit()
        config = result.scalars().first()
        return config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"upsert_chatbot_config failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/chat", response_model=ChatOut)
async def chatbot_chat(
    body: ChatIn,
    db: AsyncSession = Depends(get_db),
):
    """PUBLIC — no auth required. Visitor sends message to the bot."""
    try:
        org_id = body.org_id
        visitor_id = body.visitor_id

        # Get or create conversation
        conv = (
            await db.execute(
                select(ChatbotConversation).where(
                    ChatbotConversation.org_id == org_id,
                    ChatbotConversation.visitor_id == visitor_id,
                    ChatbotConversation.escalated_at.is_(None),
                ).order_by(ChatbotConversation.created_at.desc())
            )
        ).scalars().first()

        if conv is None:
            conv = ChatbotConversation(
                org_id=org_id,
                visitor_id=visitor_id,
                messages=[],
            )
            db.add(conv)
            await db.flush()

        # Search KB for matching article
        search_term = f"%{body.message}%"
        article = (
            await db.execute(
                select(KbArticle).where(
                    KbArticle.org_id == org_id,
                    KbArticle.is_published.is_(True),
                    (KbArticle.title.ilike(search_term) | KbArticle.body.ilike(search_term)),
                ).limit(1)
            )
        ).scalars().first()

        if article:
            reply = article.body[:500] if len(article.body) > 500 else article.body
        else:
            reply = "I'm sorry, I couldn't find an answer to your question. Would you like to speak with a team member?"

        # Append messages
        messages = list(conv.messages or [])
        messages.append({"role": "visitor", "content": body.message, "ts": datetime.now(timezone.utc).isoformat()})
        messages.append({"role": "bot", "content": reply, "ts": datetime.now(timezone.utc).isoformat()})
        conv.messages = messages
        conv.updated_at = datetime.now(timezone.utc)

        # Check escalation
        config = (
            await db.execute(
                select(ChatbotConfig).where(ChatbotConfig.org_id == org_id)
            )
        ).scalars().first()
        threshold = config.escalation_threshold if config else 3

        escalated = False
        if conv.escalated_at is None and len(messages) > threshold * 2:
            conv.escalated_at = datetime.now(timezone.utc)
            escalated = True

        await db.commit()
        await db.refresh(conv)

        return ChatOut(conversation_id=conv.id, reply=reply, escalated=escalated)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"chatbot_chat failed: {e}", extra={"org_id": str(body.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/conversations", response_model=list[ChatbotConversationOut])
async def list_conversations(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    visitor_id: Optional[uuid.UUID] = Query(default=None),
):
    try:
        org_id = _org_id(ctx)
        q = select(ChatbotConversation).where(ChatbotConversation.org_id == org_id)
        if visitor_id:
            q = q.where(ChatbotConversation.visitor_id == visitor_id)
        q = q.order_by(ChatbotConversation.created_at.desc())
        rows = (await db.execute(q)).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_conversations failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/conversations/{conversation_id}", response_model=ChatbotConversationOut)
async def get_conversation(
    conversation_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        conv = await db.get(ChatbotConversation, conversation_id)
        if not conv or conv.org_id != org_id:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conv
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_conversation failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
