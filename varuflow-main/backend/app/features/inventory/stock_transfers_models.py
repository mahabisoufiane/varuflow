"""SQLAlchemy models for multi-warehouse stock transfers (Item 38, v53)."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StockTransferStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    IN_TRANSIT = "IN_TRANSIT"
    # ``PARTIAL`` is the intermediate state reached when the receiving
    # side has booked some but not all shipped units — commonly used
    # to surface a receipt discrepancy while keeping the transfer
    # alive so the remainder can still be reconciled.
    PARTIAL = "PARTIAL"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"


class StockTransfer(Base):
    __tablename__ = "stock_transfers"
    __table_args__ = (
        CheckConstraint(
            "from_warehouse_id <> to_warehouse_id",
            name="ck_stock_transfers_distinct_warehouses",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    to_warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[StockTransferStatus] = mapped_column(
        Enum(StockTransferStatus, name="stock_transfer_status"),
        default=StockTransferStatus.DRAFT,
        nullable=False,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    shipped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    items: Mapped[list["StockTransferItem"]] = relationship(
        "StockTransferItem",
        back_populates="transfer",
        cascade="all, delete-orphan",
    )


class StockTransferItem(Base):
    __tablename__ = "stock_transfer_items"
    __table_args__ = (
        CheckConstraint("qty_requested > 0", name="ck_sti_requested_positive"),
        CheckConstraint("qty_shipped >= 0", name="ck_sti_shipped_nonneg"),
        CheckConstraint("qty_received >= 0", name="ck_sti_received_nonneg"),
        CheckConstraint("qty_shipped <= qty_requested", name="ck_sti_shipped_le_requested"),
        CheckConstraint("qty_received <= qty_shipped", name="ck_sti_received_le_shipped"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    transfer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stock_transfers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_batches.id", ondelete="SET NULL"),
        nullable=True,
    )
    qty_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    qty_shipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    qty_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    transfer: Mapped["StockTransfer"] = relationship(
        "StockTransfer", back_populates="items",
    )
