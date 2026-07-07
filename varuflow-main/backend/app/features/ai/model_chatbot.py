"""SQLAlchemy models for chatbot config and conversations (Sprint 11)."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ChatbotConfig(Base):
    __tablename__ = "chatbot_configs"
    __table_args__ = (
        UniqueConstraint("org_id", name="uq_chatbot_configs_org"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    welcome_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_threshold: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="3"
    )
    knowledge_base_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    handoff_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Bot reply when no KB/LLM answer is found; None → built-in default
    # (services/portal_chatbot.FALLBACK_REPLY).
    fallback_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )


class ChatbotConversation(Base):
    __tablename__ = "chatbot_conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    visitor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("live_chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    messages: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    escalated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
