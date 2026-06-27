"""Lead form models: LeadForm and LeadFormSubmission."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LeadForm(Base):
    __tablename__ = "lead_forms"
    __table_args__ = (
        Index("ix_lead_forms_org_id", "org_id"),
        Index("ix_lead_forms_slug", "slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    fields: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    redirect_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    notify_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    submissions: Mapped[list["LeadFormSubmission"]] = relationship(
        "LeadFormSubmission", back_populates="form", cascade="all, delete-orphan"
    )


class LeadFormSubmission(Base):
    __tablename__ = "lead_form_submissions"
    __table_args__ = (
        Index("ix_lead_form_submissions_form_id", "form_id"),
        Index("ix_lead_form_submissions_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lead_forms.id", ondelete="CASCADE"), nullable=False
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    submitter_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    submitter_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    converted_to_deal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    form: Mapped["LeadForm"] = relationship("LeadForm", back_populates="submissions")
