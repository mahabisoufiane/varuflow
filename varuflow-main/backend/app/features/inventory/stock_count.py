"""Item 14 — Stock count (cycle-count) tables.

A "stock count" is a warehouse operator counting physical stock for a
selection of products, entered in an offline-capable mobile flow. On
submit, the backend compares counted_qty against the current
StockLevel.quantity and, per item, either records nothing (match) or
creates an ``ADJUSTMENT`` StockMovement equal to the variance. Every
mutation flows through the same audit + movement ledger as manual
adjustments, so cycle counts never silently rewrite stock.

Offline constraints:
  * The mobile client assigns its own row UUIDs so the same draft
    submitted twice (e.g. queued sync retries after a network error)
    remains idempotent on the server — we upsert by id.
  * The status column transitions DRAFT → SUBMITTED → SYNCED. Once
    SYNCED the server refuses further mutations except cancel.
"""
from __future__ import annotations

from typing import Optional

import enum
import uuid

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StockCountStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    SYNCED = "SYNCED"
    CANCELLED = "CANCELLED"


class StockCount(Base):
    __tablename__ = "stock_counts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("warehouses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    status: Mapped[StockCountStatus] = mapped_column(
        Enum(StockCountStatus, name="stock_count_status"),
        nullable=False,
        default=StockCountStatus.DRAFT,
    )
    note: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    submitted_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    synced_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    items: Mapped[list["StockCountItem"]] = relationship(
        "StockCountItem",
        back_populates="stock_count",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class StockCountItem(Base):
    __tablename__ = "stock_count_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    stock_count_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stock_counts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_batches.id", ondelete="SET NULL"),
        nullable=True,
    )
    expected_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    counted_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Persisted even though it's derivable — makes the variance analytics
    # endpoint a pure SUM aggregate instead of a per-row computation.
    variance_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    stock_count: Mapped["StockCount"] = relationship(
        "StockCount", back_populates="items"
    )
