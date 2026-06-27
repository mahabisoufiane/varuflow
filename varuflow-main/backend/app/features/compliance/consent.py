"""GDPR Consent Management models."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ConsentRecord(Base):
    """A single consent event for a customer on a specific consent type."""
    __tablename__ = "consent_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    # marketing_email / sms_marketing / whatsapp / data_processing / analytics_cookies
    consent_type: Mapped[str] = mapped_column(String(80), nullable=False)
    # given / withdrawn
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="given")
    # portal / form / import / staff
    collected_via: Mapped[str] = mapped_column(String(40), nullable=False, default="staff")
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ISO timestamp when consent was given
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # ISO timestamp when consent expires / needs revalidation (default: 2 years)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        Index("ix_consent_records_org_customer", "org_id", "customer_id"),
        Index("ix_consent_records_org_type", "org_id", "consent_type", "status"),
    )


class ConsentAuditLog(Base):
    """Immutable append-only log of every consent event."""
    __tablename__ = "consent_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    consent_record_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)  # consent_given / consent_withdrawn / dsar_submitted / data_deleted
    consent_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    actor: Mapped[str | None] = mapped_column(String(200), nullable=True)  # email or "customer" or "system"
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DsarRequest(Base):
    """Data Subject Access Request (GDPR Art. 15/17/16 requests)."""
    __tablename__ = "dsar_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # access / deletion / rectification / portability / restriction
    request_type: Mapped[str] = mapped_column(String(40), nullable=False, default="access")
    requester_name: Mapped[str] = mapped_column(String(300), nullable=False)
    requester_email: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # pending / in_progress / completed / rejected
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    response_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_package_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        Index("ix_dsar_requests_org_status", "org_id", "status"),
    )
