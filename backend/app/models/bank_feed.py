"""Bank feed models.

Tables:
  bank_accounts     — one account per org (manual CSV-import)
  bank_transactions — imported transactions; deduplication via UniqueConstraint
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Date,
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


class BankAccount(Base):
    __tablename__ = "bank_accounts"
    __table_args__ = (
        Index("ix_bank_accounts_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    iban: Mapped[str | None] = mapped_column(String(34), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="SEK", nullable=False)
    last_synced_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    transactions: Mapped[list[BankTransaction]] = relationship(
        "BankTransaction", back_populates="account", cascade="all, delete-orphan"
    )


class BankTransaction(Base):
    __tablename__ = "bank_transactions"
    __table_args__ = (
        UniqueConstraint("bank_account_id", "transaction_date", "amount", "description", name="uq_bank_tx_dedup"),
        Index("ix_bank_transactions_account_id", "bank_account_id"),
        Index("ix_bank_transactions_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bank_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False
    )
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    transaction_date: Mapped[Date] = mapped_column(Date, nullable=False)
    value_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)  # negative=debit, positive=credit
    description: Mapped[str] = mapped_column(Text, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="UNMATCHED", nullable=False)  # UNMATCHED|MATCHED|EXCLUDED
    matched_type: Mapped[str | None] = mapped_column(String(30), nullable=True)  # INVOICE|EXPENSE|PAYMENT|MANUAL
    matched_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    imported_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    account: Mapped[BankAccount] = relationship("BankAccount", back_populates="transactions")
