import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class IntegrationConfig(Base):
    """Unified credential store for all third-party integrations.

    The `config` JSONB field holds provider-specific credentials.
    Treat every value inside `config` as PII — do not log or expose in responses.
    """
    __tablename__ = "integration_configs"
    __table_args__ = (
        UniqueConstraint("org_id", "provider", name="uq_integration_configs_org_provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[Any] = mapped_column(JSONB(), nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class NotificationChannel(Base):
    """Slack or Teams incoming webhook subscription per org."""
    __tablename__ = "notification_channels"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    channel_type: Mapped[str] = mapped_column(String(20), nullable=False)  # slack | teams
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    webhook_url: Mapped[str] = mapped_column(Text(), nullable=False)
    events: Mapped[Any] = mapped_column(JSONB(), nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    last_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
