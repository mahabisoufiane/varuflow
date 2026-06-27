"""Per-customer notification preferences (one row per org+customer pair)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CustomerNotificationPref(Base):
    __tablename__ = "customer_notification_prefs"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "customer_id", name="uq_customer_notification_prefs_org_customer"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    remind_1_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    remind_1_hour: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    channel_push: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    channel_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    channel_sms: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )
