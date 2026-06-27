import uuid
from datetime import datetime
from typing import Any, Optional
from sqlalchemy import String, Boolean, DateTime, UniqueConstraint, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class HomeScreenWidget(Base):
    """Home screen widget configuration per user/platform."""
    __tablename__ = "home_screen_widgets"
    __table_args__ = (
        UniqueConstraint("org_id", "user_id", "widget_type", "platform", name="uq_home_screen_widgets_org_user_type_platform"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    widget_type: Mapped[str] = mapped_column(String(50), nullable=False)  # today_bookings/today_revenue/low_stock/lock_screen_alerts
    platform: Mapped[str] = mapped_column(String(20), nullable=False)  # ios/android
    widget_size: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")  # small/medium/large
    config: Mapped[Optional[Any]] = mapped_column(JSONB(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    last_rendered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class WidgetDataSnapshot(Base):
    """Cached snapshot of widget data for fast reads."""
    __tablename__ = "widget_data_snapshots"
    __table_args__ = (
        UniqueConstraint("org_id", "widget_type", name="uq_widget_data_snapshots_org_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    widget_type: Mapped[str] = mapped_column(String(50), nullable=False)
    snapshot: Mapped[Any] = mapped_column(JSONB(), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
