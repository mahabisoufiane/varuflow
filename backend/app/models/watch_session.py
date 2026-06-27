import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, UniqueConstraint, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class WatchSession(Base):
    """Paired Apple Watch / Wear OS session."""
    __tablename__ = "watch_sessions"
    __table_args__ = (
        UniqueConstraint("org_id", "user_id", "device_id", name="uq_watch_sessions_org_user_device"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)  # apple_watch/wear_os
    device_id: Mapped[str] = mapped_column(String(200), nullable=False)
    session_token_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    paired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
