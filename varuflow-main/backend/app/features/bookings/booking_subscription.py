"""Booking subscription model — recurring scheduled appointments for customers."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BookingSubscription(Base):
    __tablename__ = "booking_subscriptions"
    __table_args__ = (
        Index("ix_booking_subscriptions_next_booking_date", "next_booking_date"),
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
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
    )
    staff_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    # 0=Monday … 6=Sunday
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[str] = mapped_column(String(8), nullable=False)  # HH:MM
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False, default="weekly")
    # active | paused | cancelled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    starts_on: Mapped[date] = mapped_column(Date(), nullable=False)
    ends_on: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    last_booked_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    next_booking_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )
