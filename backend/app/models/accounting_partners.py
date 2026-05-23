"""ORM models for the accounting firm partner program."""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.services.encryption import EncryptedString


class AccountingFirmPartner(Base):
    __tablename__ = "accounting_firm_partners"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firm_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_email: Mapped[str] = mapped_column(EncryptedString(1000), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(EncryptedString(1000), nullable=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="SE")
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    referral_code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    commission_rate_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("25"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    bank_account: Mapped[str | None] = mapped_column(EncryptedString(2000), nullable=True)
    vat_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    business_registration_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    client_count_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    application_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    referrals: Mapped[list["AccountingPartnerReferral"]] = relationship(
        "AccountingPartnerReferral", back_populates="partner", cascade="all, delete-orphan"
    )

    # Valid statuses
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_ACTIVE = "active"
    STATUS_PAUSED = "paused"
    STATUS_TERMINATED = "terminated"


class AccountingPartnerReferral(Base):
    __tablename__ = "accounting_partner_referrals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounting_firm_partners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    referred_org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="clicked")
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signed_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    subscription_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    commission_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    months_remaining: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    partner: Mapped["AccountingFirmPartner"] = relationship("AccountingFirmPartner", back_populates="referrals")

    # Valid statuses
    STATUS_CLICKED = "clicked"
    STATUS_SIGNED_UP = "signed_up"
    STATUS_CONVERTED = "converted"
    STATUS_PAID_OUT = "paid_out"
    STATUS_EXPIRED = "expired"
