"""Portal notification preferences model (Feature 19)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PortalNotificationPreference(Base):
    __tablename__ = "portal_notification_preferences"
    __table_args__ = (
        UniqueConstraint("customer_id", name="uq_portal_notif_prefs_customer"),
        Index("ix_portal_notif_prefs_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    invoice_created: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    payment_received: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    quote_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    appointment_reminder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    marketing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
