"""Performance review models: PerformanceCycle and PerformanceReview."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PerformanceCycle(Base):
    __tablename__ = "performance_cycles"
    __table_args__ = (
        Index("ix_performance_cycles_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    cycle_frequency: Mapped[str] = mapped_column(String(20), nullable=False, default="annual")
    rating_labels: Mapped[list] = mapped_column(
        JSONB, nullable=False,
        default=lambda: ["Unsatisfactory", "Below Expectations", "Meets Expectations",
                         "Exceeds Expectations", "Outstanding"]
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    reviews: Mapped[list["PerformanceReview"]] = relationship(
        "PerformanceReview", back_populates="cycle", cascade="all, delete-orphan"
    )


class PerformanceReview(Base):
    __tablename__ = "performance_reviews"
    __table_args__ = (
        UniqueConstraint("cycle_id", "staff_id", name="uq_perf_review_cycle_staff"),
        Index("ix_performance_reviews_org_id", "org_id"),
        Index("ix_performance_reviews_cycle_id", "cycle_id"),
        Index("ix_performance_reviews_staff_id", "staff_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    cycle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("performance_cycles.id", ondelete="CASCADE"), nullable=False
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_staff_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id", ondelete="SET NULL"), nullable=True
    )
    goals: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    self_assessment: Mapped[str | None] = mapped_column(Text, nullable=True)
    manager_review: Mapped[str | None] = mapped_column(Text, nullable=True)
    overall_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    check_in_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    development_plan: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    cycle: Mapped["PerformanceCycle"] = relationship("PerformanceCycle", back_populates="reviews")
