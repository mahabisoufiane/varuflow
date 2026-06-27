"""SQLAlchemy model for return pickup requests (Sprint 11)."""
from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ReturnPickupRequest(Base):
    __tablename__ = "return_pickup_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    return_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    courier_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pickup_address_line1: Mapped[str] = mapped_column(String(200), nullable=False)
    pickup_address_city: Mapped[str] = mapped_column(String(100), nullable=False)
    pickup_postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pickup_country: Mapped[str] = mapped_column(
        String(2), nullable=False, server_default="SE"
    )
    preferred_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    preferred_time_slot: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="morning"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )
    courier_tracking_number: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    courier_booked_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
