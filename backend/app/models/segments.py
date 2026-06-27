"""SQLAlchemy models for customer segmentation (Item 39, v54)."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SegmentType(str, enum.Enum):
    # Membership resolved by the rule engine; recomputed on a schedule.
    AUTO = "AUTO"
    # Membership managed by the operator — add/remove customers manually.
    MANUAL = "MANUAL"


class Segment(Base):
    __tablename__ = "segments"
    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_segments_org_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[SegmentType] = mapped_column(
        Enum(SegmentType, name="segment_type"),
        nullable=False,
    )
    # Free-form JSON so the rule grammar can grow without a migration.
    # AUTO segments use it; MANUAL segments leave it as ``{}``.
    rules: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict,
    )
    customer_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    last_computed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    members: Mapped[list["SegmentMember"]] = relationship(
        "SegmentMember",
        back_populates="segment",
        cascade="all, delete-orphan",
    )


class SegmentMember(Base):
    __tablename__ = "segment_members"
    __table_args__ = (
        UniqueConstraint(
            "segment_id", "customer_id",
            name="uq_segment_members_segment_customer",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    segment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("segments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    segment: Mapped["Segment"] = relationship(
        "Segment", back_populates="members",
    )
