from __future__ import annotations

import enum
import uuid
from datetime import datetime  # noqa: F401 — resolved by Mapped[datetime | None]
from decimal import Decimal

from app.services.encryption import EncryptedString
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InvoiceStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    PAID = "PAID"
    OVERDUE = "OVERDUE"


class PaymentMethod(str, enum.Enum):
    BANK_TRANSFER = "BANK_TRANSFER"
    CARD = "CARD"
    CASH = "CASH"
    OTHER = "OTHER"


class RecurringFrequency(str, enum.Enum):
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    org_number: Mapped[str | None] = mapped_column(String(20))  # Swedish org number
    vat_number: Mapped[str | None] = mapped_column(String(30))
    # Item 28 — PII encrypted at rest via EncryptedString. Columns were
    # widened in migration v46 to accommodate Fernet ciphertext overhead
    # (~100 bytes + 4/3x Base64 blow-up). Legacy plaintext rows still
    # decrypt transparently so the rollout is zero-downtime.
    email: Mapped[str | None] = mapped_column(EncryptedString(512))
    phone: Mapped[str | None] = mapped_column(EncryptedString(256))
    # v40 (Item 18) — opt-in WhatsApp contact. Populated on the
    # customer edit form; stored as a loosely-formatted string mirroring
    # ``phone``. Normalisation to E.164 (+46…) happens in
    # ``app.services.whatsapp`` so we never reject a paste from the UI;
    # an unparseable value short-circuits the WhatsApp channel and the
    # dunning sweep falls back to email-only.
    whatsapp_number: Mapped[str | None] = mapped_column(EncryptedString(256), nullable=True)
    address: Mapped[str | None] = mapped_column(EncryptedString(1024))
    payment_terms_days: Mapped[int] = mapped_column(
        Integer, default=30, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # v22 — owner-controlled toggle that exposes the self-service
    # ordering UI inside the customer portal. Off by default so rolling
    # out the feature doesn't surprise every existing portal user.
    portal_ordering_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false",
    )
    # v39 (Item 17) — Peppol Business Identifier (eg "0007:5567321234") and
    # opt-in flag. Auto-send via Peppol only fires when BOTH the flag is
    # true AND a valid peppol_id is present.  Kept optional so customers
    # onboarded before v39 keep working unchanged.
    peppol_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    peppol_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false",
    )
    # v55 (Item 40) — marketing-email opt-out. Flipped by the public
    # /api/campaigns/unsubscribe endpoint (signed token; no auth) and
    # read by the campaign dispatcher before every send. Transactional
    # mail (invoices, dunning, receipts) intentionally ignores this
    # flag — it's marketing consent only.
    email_opted_out: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false",
    )
    email_opted_out_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice", back_populates="customer"
    )
    recurring_invoices: Mapped[list["RecurringInvoice"]] = relationship(
        "RecurringInvoice", back_populates="customer"
    )


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        # Enforced at DB level by migration v15. Prevents concurrent
        # invoice creation from producing duplicate INV-YYYY-NNNN numbers
        # within the same tenant — a bokföringslagen compliance violation.
        UniqueConstraint("org_id", "invoice_number", name="uq_invoices_org_invoice_number"),
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
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False)
    issue_date: Mapped[Date] = mapped_column(Date, nullable=False)
    due_date: Mapped[Date] = mapped_column(Date, nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, name="invoice_status"),
        default=InvoiceStatus.DRAFT,
        nullable=False,
    )
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    vat_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    total_sek: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    # v50 (Item 34) — currency & exchange-rate snapshot. ``currency``
    # is the ISO code the invoice was issued in; ``exchange_rate`` is
    # the rate (invoice currency → org base currency) at issue time.
    # Analytics normalise historical rows by multiplying by this rate.
    # ``total_sek`` is a legacy name kept for backwards compatibility
    # — it stores the total in the invoice's currency regardless.
    currency: Mapped[str] = mapped_column(String(3), default="SEK", nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), default=Decimal("1"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    # Stripe payment link
    stripe_payment_link_url: Mapped[str | None] = mapped_column(String(500))
    stripe_payment_link_status: Mapped[str | None] = mapped_column(String(20))  # pending / paid / expired
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(String(200))
    # v20 — dunning automation
    dunning_stage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_dunning_sent_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # v48 (Item 32) — optional staff attribution for commission tracking.
    # NULL for tenants that don't assign invoices to a staff member;
    # the commission hook skips silently when this is NULL.
    staff_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staff.id", ondelete="SET NULL"),
        nullable=True,
    )
    # gov1: approval workflow — null=not required, pending/approved/rejected
    approval_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Link back to quote that originated this invoice
    quote_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("quotes.id", ondelete="SET NULL"), nullable=True)
    available_payment_methods: Mapped[str | None] = mapped_column(String(200), nullable=True)
    early_payment_discount_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    early_payment_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    invoice_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="standard")
    deposit_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    parent_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    customer: Mapped["Customer"] = relationship("Customer", back_populates="invoices")
    line_items: Mapped[list["InvoiceLineItem"]] = relationship(
        "InvoiceLineItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment", back_populates="invoice", cascade="all, delete-orphan"
    )


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("25.00"), nullable=False
    )
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="line_items")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    payment_date: Mapped[Date] = mapped_column(Date, nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method"),
        default=PaymentMethod.BANK_TRANSFER,
        nullable=False,
    )
    reference: Mapped[str | None] = mapped_column(String(255))
    # v50 (Item 34) — currency snapshot per payment. Lets a single
    # invoice accept mixed-currency payments (e.g. EUR cash + SEK
    # bank transfer) while preserving historical rates.
    currency: Mapped[str] = mapped_column(String(3), default="SEK", nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), default=Decimal("1"), nullable=False
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="payments")


class CustomerPortalToken(Base):
    __tablename__ = "customer_portal_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    customer: Mapped["Customer"] = relationship("Customer")


class RecurringInvoice(Base):
    __tablename__ = "recurring_invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    frequency: Mapped[RecurringFrequency] = mapped_column(
        Enum(RecurringFrequency, name="recurring_frequency"), nullable=False
    )
    next_run_date: Mapped[Date] = mapped_column(Date, nullable=False)
    template_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # v39 (Item 17) — if True, the scheduler auto-sends every generated
    # invoice according to ``auto_send_method`` instead of leaving it in
    # DRAFT for the owner to click Send. ``auto_send_method`` is a simple
    # comma-separated string so we can later add "sms" or "whatsapp"
    # without a schema migration. Supported values today:
    #   • "email"        — PDF via Resend (requires customer.email).
    #   • "peppol"       — Peppol XML (requires customer.peppol_enabled).
    #   • "email,peppol" — both.
    auto_send: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false",
    )
    auto_send_method: Mapped[str] = mapped_column(
        String(32), default="email", nullable=False, server_default="email",
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    customer: Mapped["Customer"] = relationship(
        "Customer", back_populates="recurring_invoices"
    )
