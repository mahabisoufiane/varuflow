"""Point-of-Sale models: sessions, sales, sale items."""
from __future__ import annotations

from typing import Optional

import enum
import uuid
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PosPaymentMethod(str, enum.Enum):
    CASH = "CASH"
    CARD = "CARD"
    SWISH = "SWISH"
    OTHER = "OTHER"


class PosSessionStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class PosSession(Base):
    __tablename__ = "pos_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    cashier_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[PosSessionStatus] = mapped_column(
        Enum(PosSessionStatus, name="pos_session_status"),
        default=PosSessionStatus.OPEN, nullable=False,
    )
    opened_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    closed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    # Cash-drawer reconciliation (v34). Nullable for sessions opened
    # before the tablet POS redesign — we cannot invent historical floats.
    opening_float: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    counted_cash: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    variance: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    sales: Mapped[list["PosSale"]] = relationship("PosSale", back_populates="session")


class PosSale(Base):
    __tablename__ = "pos_sales"
    __table_args__ = (
        # DB-level safety net behind the FOR UPDATE lock in create_sale.
        # Enforced by migration v16.
        UniqueConstraint("org_id", "sale_number", name="uq_pos_sales_org_sale_number"),
        # Idempotency key for offline-sync batch replay. Partial (nullable)
        # so sessions predating the tablet POS redesign aren't affected.
        UniqueConstraint("org_id", "offline_id", name="uq_pos_sales_offline_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_sessions.id", ondelete="CASCADE"), nullable=False,
    )
    sale_number: Mapped[str] = mapped_column(String(50), nullable=False)
    # Client-generated UUID set by the tablet when a sale is queued
    # offline. The backend checks this before inserting to avoid duplicate
    # sales when the sync queue replays after a dropped connection.
    offline_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # v50 (Item 34) — currency snapshot per sale so a till can switch
    # between EUR / USD / SEK on consecutive transactions.
    currency: Mapped[str] = mapped_column(String(3), default="SEK", nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), default=Decimal("1"), nullable=False
    )
    payment_method: Mapped[PosPaymentMethod] = mapped_column(
        Enum(PosPaymentMethod, name="pos_payment_method"),
        default=PosPaymentMethod.CASH, nullable=False,
    )
    amount_tendered: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))  # cash given
    change_due: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    # v48 (Item 32) — optional staff attribution for commission tracking.
    # NULL for tills that don't capture who rang up the sale; the
    # commission hook skips silently when this is NULL.
    staff_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staff.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_refunded: Mapped[bool] = mapped_column(default=False, nullable=False)
    refunded_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session: Mapped["PosSession"] = relationship("PosSession", back_populates="sales")
    items: Mapped[list["PosSaleItem"]] = relationship("PosSaleItem", back_populates="sale", cascade="all, delete-orphan")


class PosSaleItem(Base):
    __tablename__ = "pos_sale_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_sales.id", ondelete="CASCADE"), nullable=False,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True,
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("25.00"))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    sale: Mapped["PosSale"] = relationship("PosSale", back_populates="items")
