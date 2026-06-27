"""Supplier credit note (Item 92).

Mirror of the customer credit-note model (Item 70) but flowing in
the reverse direction: a supplier issues a credit to the tenant.
Credits may optionally reference a source purchase order.
"""
from __future__ import annotations

from typing import Optional

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date, DateTime, Enum, ForeignKey, Integer, Numeric, String,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SupplierCreditNoteStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    VOIDED = "VOIDED"


class SupplierCreditNote(Base):
    __tablename__ = "supplier_credit_notes"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "number", name="uq_supplier_credit_notes_org_number",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_orders.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[SupplierCreditNoteStatus] = mapped_column(
        Enum(SupplierCreditNoteStatus, name="supplier_credit_note_status"),
        default=SupplierCreditNoteStatus.DRAFT, nullable=False, index=True,
    )
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), default="SEK", nullable=False,
    )
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False,
    )
    tax_total: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False,
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False,
    )
    issued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    voided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    void_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )

    lines: Mapped[list["SupplierCreditNoteLine"]] = relationship(
        "SupplierCreditNoteLine",
        back_populates="supplier_credit_note",
        cascade="all, delete-orphan",
        order_by="SupplierCreditNoteLine.position",
    )


class SupplierCreditNoteLine(Base):
    __tablename__ = "supplier_credit_note_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    supplier_credit_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("supplier_credit_notes.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("25.00"), nullable=False,
    )
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    supplier_credit_note: Mapped[SupplierCreditNote] = relationship(
        "SupplierCreditNote", back_populates="lines",
    )
