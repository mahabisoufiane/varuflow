"""MobileKpiConfig model — Sprint 13: Reporting + AI Across the Stack."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MobileKpiConfig(Base):
    __tablename__ = "mobile_kpi_configs"
    __table_args__ = (
        UniqueConstraint("org_id", "user_id", name="uq_mobile_kpi_configs_org_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    kpi_ids: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    notification_deep_links_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    refresh_interval_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="15"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
