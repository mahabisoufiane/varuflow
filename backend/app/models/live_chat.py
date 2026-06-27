"""SQLAlchemy models for live chat sessions and messages (Sprint 11)."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class LiveChatSession(Base):
    __tablename__ = "live_chat_sessions"

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
    visitor_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    visitor_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    assigned_staff_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="open"
    )
    page_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )


class LiveChatMessage(Base):
    __tablename__ = "live_chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("live_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_type: Mapped[str] = mapped_column(String(10), nullable=False)
    sender_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
