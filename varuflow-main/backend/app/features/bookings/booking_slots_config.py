"""SQLAlchemy model for booking slots configuration (Sprint 11)."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class BookingSlotsConfig(Base):
    __tablename__ = "booking_slots_config"
    __table_args__ = (
        UniqueConstraint(
            "org_id",
            "service_id",
            "staff_id",
            "period_type",
            name="uq_booking_slots_config_org_service_staff_period",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    staff_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    period_type: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="week"
    )
    total_slots: Mapped[int] = mapped_column(Integer, nullable=False, server_default="20")
    show_urgency_below: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="5"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
