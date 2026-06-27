"""SQLAlchemy model for message translations (Sprint 12)."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class MessageTranslation(Base):
    __tablename__ = "message_translations"
    __table_args__ = (
        UniqueConstraint(
            "message_id", "target_language", name="uq_message_translations_msg_lang"
        ),
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
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("unified_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_language: Mapped[str] = mapped_column(String(5), nullable=False)
    target_language: Mapped[str] = mapped_column(String(5), nullable=False)
    translated_body: Mapped[str] = mapped_column(Text, nullable=False)
    translated_by: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="openai"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
