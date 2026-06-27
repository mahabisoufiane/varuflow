"""Investor updates — periodic investor communication and distribution."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InvestorUpdate(Base):
    __tablename__ = "investor_updates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    period_month: Mapped[Optional[datetime]] = mapped_column(Date(), nullable=True)
    # draft | sent
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    revenue_snapshot: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    burn_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    runway_months: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 1), nullable=True)
    key_wins: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    challenges: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    next_milestones: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    generated_pdf_url: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    recipients: Mapped[list["InvestorUpdateRecipient"]] = relationship(
        "InvestorUpdateRecipient", back_populates="update", cascade="all, delete-orphan"
    )


class InvestorUpdateRecipient(Base):
    __tablename__ = "investor_update_recipients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    update_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investor_updates.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    update: Mapped["InvestorUpdate"] = relationship(
        "InvestorUpdate", back_populates="recipients"
    )
