from __future__ import annotations
import uuid
from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class MerchantCalendarSync(Base):
    __tablename__ = "merchant_calendar_syncs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    access_token: Mapped[str | None] = mapped_column(nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(nullable=True)
    token_expiry: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    calendar_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sync_direction: Mapped[str] = mapped_column(String(10), server_default="both", nullable=False)
    last_synced_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
