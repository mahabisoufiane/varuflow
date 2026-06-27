"""A/B testing — tests and variants for email campaign optimization."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AbTest(Base):
    __tablename__ = "ab_tests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    # open_rate | click_rate | conversion_rate
    test_metric: Mapped[str] = mapped_column(String(30), nullable=False, default="open_rate")
    # draft | running | complete
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    winner_variant: Mapped[Optional[str]] = mapped_column(String(1), nullable=True)
    auto_promote: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    variants: Mapped[list["AbTestVariant"]] = relationship(
        "AbTestVariant", back_populates="ab_test", cascade="all, delete-orphan"
    )


class AbTestVariant(Base):
    __tablename__ = "ab_test_variants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ab_test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ab_tests.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # A or B
    variant: Mapped[str] = mapped_column(String(1), nullable=False)
    subject_line: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    body_html: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    recipient_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("50"))
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    open_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    click_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conversion_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    ab_test: Mapped["AbTest"] = relationship("AbTest", back_populates="variants")
