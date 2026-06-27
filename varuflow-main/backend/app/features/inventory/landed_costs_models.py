"""LandedCostCharge and LandedCostLine SQLAlchemy models."""
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
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LandedCostCharge(Base):
    __tablename__ = "landed_cost_charges"
    __table_args__ = (
        Index("ix_landed_cost_charges_org_id", "org_id"),
        Index("ix_landed_cost_charges_po_id", "purchase_order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    purchase_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True
    )
    charge_type: Mapped[str] = mapped_column(String(40), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="SEK")
    distribution_method: Mapped[str] = mapped_column(String(20), nullable=False, server_default="by_value")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    lines: Mapped[list["LandedCostLine"]] = relationship(
        "LandedCostLine", back_populates="charge", cascade="all, delete-orphan"
    )


class LandedCostLine(Base):
    __tablename__ = "landed_cost_lines"
    __table_args__ = (
        Index("ix_landed_cost_lines_charge_id", "charge_id"),
        Index("ix_landed_cost_lines_product_id", "product_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    charge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("landed_cost_charges.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    purchase_order_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    unit_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    item_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    applied_unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)

    charge: Mapped["LandedCostCharge"] = relationship("LandedCostCharge", back_populates="lines")
