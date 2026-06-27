"""Decision Log — structured record of organisational decisions."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DecisionEntry(Base):
    __tablename__ = "decision_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    decided_at: Mapped[date] = mapped_column(Date(), nullable=False)
    decided_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    decided_by_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # product | finance | hr | operations | strategy | other
    area: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    decision_summary: Mapped[str] = mapped_column(Text(), nullable=False)
    alternatives_considered: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    expected_outcome: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    actual_outcome: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    # pending | in_progress | completed | reversed
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )
