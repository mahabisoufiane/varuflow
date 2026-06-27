"""Customer app models — push tokens and per-org app configuration."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CustomerAppPushToken(Base):
    __tablename__ = "customer_app_push_tokens"
    __table_args__ = (
        UniqueConstraint("customer_id", "token", name="uq_customer_app_push_token"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    token: Mapped[str] = mapped_column(String(500), nullable=False)
    # ios | android | web
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    app_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CustomerAppConfig(Base):
    __tablename__ = "customer_app_config"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    app_name: Mapped[str] = mapped_column(String(100), nullable=False)
    primary_color: Mapped[str] = mapped_column(
        String(7), nullable=False, default="#1a2332"
    )
    secondary_color: Mapped[str] = mapped_column(
        String(7), nullable=False, default="#ffffff"
    )
    logo_url: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    welcome_message: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    features_enabled: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    booking_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    loyalty_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )
