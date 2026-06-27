"""Email sequence models."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EmailSequence(Base):
    __tablename__ = "email_sequences"
    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_email_sequences_org_name"),
        Index("ix_email_sequences_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    trigger_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    trigger_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    steps: Mapped[list["EmailSequenceStep"]] = relationship(
        "EmailSequenceStep", back_populates="sequence", cascade="all, delete-orphan",
        order_by="EmailSequenceStep.step_number"
    )
    enrollments: Mapped[list["EmailSequenceEnrollment"]] = relationship(
        "EmailSequenceEnrollment", back_populates="sequence", cascade="all, delete-orphan"
    )


class EmailSequenceStep(Base):
    __tablename__ = "email_sequence_steps"
    __table_args__ = (
        UniqueConstraint("sequence_id", "step_number", name="uq_seq_step_number"),
        Index("ix_email_sequence_steps_sequence_id", "sequence_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sequence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_sequences.id", ondelete="CASCADE"), nullable=False
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    delay_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sequence: Mapped["EmailSequence"] = relationship("EmailSequence", back_populates="steps")


class EmailSequenceEnrollment(Base):
    __tablename__ = "email_sequence_enrollments"
    __table_args__ = (
        UniqueConstraint("sequence_id", "customer_id", name="uq_seq_enrollment_customer"),
        Index("ix_email_sequence_enrollments_org_id", "org_id"),
        Index("ix_email_sequence_enrollments_next_send_at", "next_send_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sequence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_sequences.id", ondelete="CASCADE"), nullable=False
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_send_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sequence: Mapped["EmailSequence"] = relationship("EmailSequence", back_populates="enrollments")
