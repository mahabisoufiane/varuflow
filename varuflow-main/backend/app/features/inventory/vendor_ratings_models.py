"""VendorManualRating and VendorRatingCache SQLAlchemy models."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VendorManualRating(Base):
    __tablename__ = "vendor_manual_ratings"
    __table_args__ = (
        Index("ix_vendor_manual_ratings_org_id", "org_id"),
        Index("ix_vendor_manual_ratings_supplier_id", "supplier_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    supplier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True
    )
    purchase_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    stars: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rated_by_staff_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    delivery_ok: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    quality_ok: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class VendorRatingCache(Base):
    __tablename__ = "vendor_rating_cache"
    __table_args__ = (
        UniqueConstraint("org_id", "supplier_id", name="uq_vendor_rating_cache_org_supplier"),
        Index("ix_vendor_rating_cache_org_id", "org_id"),
        Index("ix_vendor_rating_cache_supplier_id", "supplier_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False
    )
    on_time_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    quality_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    price_stability: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    manual_avg: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False, server_default="0")
    overall_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    po_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
