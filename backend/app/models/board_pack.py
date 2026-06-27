"""Board packs — meeting materials and KPI snapshots for board members."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BoardPack(Base):
    __tablename__ = "board_packs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    meeting_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    # draft | published
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    financial_period: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    agenda: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    executive_summary: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    kpi_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    pdf_url: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )
