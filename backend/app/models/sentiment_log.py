"""SQLAlchemy model for conversation sentiment logs (Sprint 12)."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ConversationSentimentLog(Base):
    __tablename__ = "conversation_sentiment_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("unified_inbox_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("unified_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sentiment: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    flagged_for_manager: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
