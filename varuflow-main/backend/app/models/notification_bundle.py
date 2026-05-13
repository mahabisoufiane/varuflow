from __future__ import annotations
import uuid
from datetime import time
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Time, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class NotificationBundleConfig(Base):
    __tablename__ = "notification_bundle_configs"
    __table_args__ = (
        UniqueConstraint("org_id", "user_id", "bundle_name", name="uq_notification_bundle_org_user_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    bundle_name: Mapped[str] = mapped_column(String(100), nullable=False)
    event_types: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    delivery_channel: Mapped[str] = mapped_column(String(20), server_default="in_app", nullable=False)
    schedule: Mapped[str] = mapped_column(String(20), server_default="immediate", nullable=False)
    digest_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
