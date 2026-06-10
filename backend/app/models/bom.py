"""BOM models: BomHeader and BomLine."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BomHeader(Base):
    __tablename__ = "bom_headers"
    __table_args__ = (
        Index("ix_bom_headers_org_id", "org_id"),
        Index("ix_bom_headers_product_id", "product_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    is_kit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    yield_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default="100")
    scrap_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    cost_override: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    lines: Mapped[list["BomLine"]] = relationship(
        "BomLine", back_populates="bom", cascade="all, delete-orphan"
    )


class BomLine(Base):
    __tablename__ = "bom_lines"
    __table_args__ = (
        Index("ix_bom_lines_bom_id", "bom_id"),
        Index("ix_bom_lines_component_product_id", "component_product_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    bom_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bom_headers.id", ondelete="CASCADE"), nullable=False
    )
    component_product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False, default="st")
    cost_per_unit: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    bom: Mapped["BomHeader"] = relationship("BomHeader", back_populates="lines")
