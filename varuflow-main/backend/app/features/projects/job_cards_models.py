"""Job card / field-service work order model — customer-facing, not manufacturing."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class JobCard(Base):
    __tablename__ = "job_cards"
    __table_args__ = (
        Index("ix_job_cards_org_id", "org_id"),
        Index("ix_job_cards_customer_id", "customer_id"),
        Index("ix_job_cards_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    job_number: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    assigned_staff_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    site_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scheduled_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    estimated_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # status: pending → assigned → in_progress → completed → invoiced
    customer_signature_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="SEK")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    parts: Mapped[List["JobCardPart"]] = relationship("JobCardPart", back_populates="job_card", cascade="all, delete-orphan", lazy="select")
    labour: Mapped[List["JobCardLabour"]] = relationship("JobCardLabour", back_populates="job_card", cascade="all, delete-orphan", lazy="select")
    photos: Mapped[List["JobCardPhoto"]] = relationship("JobCardPhoto", back_populates="job_card", cascade="all, delete-orphan", lazy="select")


class JobCardPart(Base):
    """Inventory product consumed during a job."""
    __tablename__ = "job_card_parts"
    __table_args__ = (Index("ix_job_card_parts_job_card_id", "job_card_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("job_cards.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False, default=Decimal("1"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    job_card: Mapped["JobCard"] = relationship("JobCard", back_populates="parts")


class JobCardLabour(Base):
    """Hours logged by a staff member on a job."""
    __tablename__ = "job_card_labour"
    __table_args__ = (Index("ix_job_card_labour_job_card_id", "job_card_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("job_cards.id", ondelete="CASCADE"), nullable=False)
    staff_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="SET NULL"), nullable=True)
    staff_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    hourly_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    job_card: Mapped["JobCard"] = relationship("JobCard", back_populates="labour")


class JobCardPhoto(Base):
    """Before / after photos attached to a job."""
    __tablename__ = "job_card_photos"
    __table_args__ = (Index("ix_job_card_photos_job_card_id", "job_card_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("job_cards.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    caption: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    photo_type: Mapped[str] = mapped_column(String(10), nullable=False, default="before")  # before | after
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    job_card: Mapped["JobCard"] = relationship("JobCard", back_populates="photos")
