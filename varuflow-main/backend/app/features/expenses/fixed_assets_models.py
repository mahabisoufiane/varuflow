"""Fixed Asset Register models.

Tables:
  fixed_assets        — capital assets with acquisition cost, depreciation method
  asset_depreciations — per-period depreciation entries, linked to journal_entries
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FixedAsset(Base):
    __tablename__ = "fixed_assets"
    __table_args__ = (
        Index("ix_fixed_assets_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(40), default="EQUIPMENT", nullable=False)
    acquisition_date: Mapped[Date] = mapped_column(Date, nullable=False)
    acquisition_cost: Mapped[Numeric] = mapped_column(Numeric(14, 2), nullable=False)
    salvage_value: Mapped[Numeric] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    useful_life_years: Mapped[int] = mapped_column(nullable=False)
    depreciation_method: Mapped[str] = mapped_column(String(30), default="STRAIGHT_LINE", nullable=False)
    current_book_value: Mapped[Numeric] = mapped_column(Numeric(14, 2), nullable=False)
    account_code: Mapped[str] = mapped_column(String(10), default="1710", nullable=False)
    supplier: Mapped[str | None] = mapped_column(String(200), nullable=True)
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    expense_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expenses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_disposed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    disposed_at: Mapped[Date | None] = mapped_column(Date, nullable=True)
    disposal_proceeds: Mapped[Numeric | None] = mapped_column(Numeric(14, 2), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    depreciations: Mapped[list[AssetDepreciation]] = relationship(
        "AssetDepreciation", back_populates="asset", cascade="all, delete-orphan"
    )


class AssetDepreciation(Base):
    __tablename__ = "asset_depreciations"
    __table_args__ = (
        UniqueConstraint("asset_id", "period", name="uq_asset_depreciation_period"),
        Index("ix_asset_dep_asset_id", "asset_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fixed_assets.id", ondelete="CASCADE"), nullable=False
    )
    period: Mapped[Date] = mapped_column(Date, nullable=False)  # first day of the period (e.g. 2025-01-01)
    amount: Mapped[Numeric] = mapped_column(Numeric(14, 2), nullable=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    asset: Mapped[FixedAsset] = relationship("FixedAsset", back_populates="depreciations")
