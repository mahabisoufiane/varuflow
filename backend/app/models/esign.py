"""E-Signature models — signing envelopes, signatories, and audit trail."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, String, Text
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ESignRequest(Base):
    """A signing envelope — one document sent to one or more signatories."""
    __tablename__ = "esign_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)  # FK to documents
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # draft / sent / partially_signed / fully_signed / declined / expired / cancelled
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    # If set, sending reminder email after this many days of inactivity
    reminder_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    signed_pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    audit_certificate_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    signatories: Mapped[list[ESignSignatory]] = relationship("ESignSignatory", back_populates="request", cascade="all, delete-orphan")
    audit_entries: Mapped[list[ESignAuditEntry]] = relationship("ESignAuditEntry", back_populates="request", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_esign_requests_org_status", "org_id", "status"),
    )


class ESignSignatory(Base):
    """A person who must sign the document."""
    __tablename__ = "esign_signatories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("esign_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    email: Mapped[str] = mapped_column(String(500), nullable=False)
    role: Mapped[str | None] = mapped_column(String(200), nullable=True)  # e.g. "CEO", "Witness"
    sign_order: Mapped[int] = mapped_column(Integer, default=1)  # 1 = sign in any order; higher = sequential
    token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)  # UUID token in signing link
    # pending / signed / declined
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # typed/drawn signature image or text
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    request: Mapped[ESignRequest] = relationship("ESignRequest", back_populates="signatories")


class ESignAuditEntry(Base):
    """Immutable event log for legal audit trail."""
    __tablename__ = "esign_audit_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("esign_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)  # created/sent/viewed/signed/declined/completed
    actor_email: Mapped[str | None] = mapped_column(String(500), nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    audit_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    request: Mapped[ESignRequest] = relationship("ESignRequest", back_populates="audit_entries")
