"""SQLAlchemy model for the upsell_events table."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UpsellEvent(Base):
    """Records every impression, click, dismissal, and conversion of an upsell."""
    __tablename__ = "upsell_events"
    __table_args__ = (
        Index("ix_upsell_events_user_shown", "user_id", "shown_at"),
    )

    id:           Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id:       Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id:      Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    trigger_id:   Mapped[str]       = mapped_column(String(80),  nullable=False, index=True)
    placement:    Mapped[str]       = mapped_column(String(20),  nullable=False, server_default="modal")
    target_tier:  Mapped[str]       = mapped_column(String(20),  nullable=False, server_default="PRO")
    ab_variant:   Mapped[str | None]= mapped_column(String(20),  nullable=True)
    shown_at:     Mapped[datetime]  = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    clicked_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
