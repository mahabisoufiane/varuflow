"""Accounts-payable invoice model (Item 20).

Separate table from sales ``invoices`` because the lifecycles diverge:
no Peppol export, no dunning, no customer-facing PDF — and the queries
that drive sales dashboards must not have to filter by direction.

The auto-create-on-PO-receipt path (see
``app.services.payables.create_payable_from_po``) writes a DRAFT row
linked to the originating ``purchase_order_id``. The unique constraint
on that column makes the auto-create call naturally idempotent — if a
draft already exists for the PO, the service returns it instead of
inserting a second one.
"""
from __future__ import annotations

from typing import Optional

import uuid
from datetime import date as _date
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PayableInvoice(Base):
    __tablename__ = "payable_invoices"
    __table_args__ = (
        # Idempotency guard: one draft per PO, ever. The auto-create
        # service short-circuits before insert when a row already
        # exists, but this constraint defends against concurrent
        # receives racing past that check.
        UniqueConstraint("purchase_order_id", name="uq_payable_invoices_po"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_orders.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Free-text status so future states (APPROVED/PAID/VOID/DISPUTED)
    # don't need an enum migration each time. The router-level schemas
    # constrain valid transitions.
    status: Mapped[str] = mapped_column(
        String(20), default="DRAFT", server_default="DRAFT", nullable=False
    )
    # Supplier's own invoice number, populated when the merchant edits
    # the draft after receiving the PDF from their supplier. Nullable
    # because the auto-create path runs before that bill arrives.
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    issue_date: Mapped[_date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[_date | None] = mapped_column(Date, nullable=True)

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), server_default="0", nullable=False
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), server_default="0", nullable=False
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), server_default="0", nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(10), default="SEK", server_default="SEK", nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    supplier = relationship("Supplier")
    purchase_order = relationship("PurchaseOrder")
