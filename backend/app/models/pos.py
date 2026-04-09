"""Point-of-Sale models: sessions, sales, sale items."""
import enum
import uuid
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, func
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

    sales: Mapped[list["PosSale"]] = relationship("PosSale", back_populates="session")


class PosSale(Base):
    __tablename__ = "pos_sales"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_sessions.id", ondelete="CASCADE"), nullable=False,
    )
    sale_number: Mapped[str] = mapped_column(String(50), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    payment_method: Mapped[PosPaymentMethod] = mapped_column(
        Enum(PosPaymentMethod, name="pos_payment_method"),
        default=PosPaymentMethod.CASH, nullable=False,
    )
    amount_tendered: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))  # cash given
    change_due: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
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
