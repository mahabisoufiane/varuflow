"""Training request and mandatory training requirement models (Feature 18)."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MandatoryTrainingRequirement(Base):
    __tablename__ = "mandatory_training_requirements"
    __table_args__ = (
        UniqueConstraint("org_id", "job_role", "training_name", name="uq_mandatory_training_org_role_name"),
        Index("ix_mandatory_training_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    job_role: Mapped[str] = mapped_column(String(100), nullable=False)
    training_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TrainingRequest(Base):
    __tablename__ = "training_requests"
    __table_args__ = (
        Index("ix_training_requests_org_id", "org_id"),
        Index("ix_training_requests_staff_id", "staff_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False
    )
    training_name: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    estimated_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # pending | approved | rejected | completed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    manager_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
