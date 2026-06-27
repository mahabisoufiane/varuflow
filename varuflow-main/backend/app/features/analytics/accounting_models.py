"""Double-entry bookkeeping models.

Three tables:
  chart_of_accounts  — BAS 2024 account definitions + custom accounts per org
  journal_entries    — one entry (verification) per bookkeeping event
  journal_lines      — debit/credit lines that compose a balanced journal entry

Design decisions:
- account_code on JournalLine is *denormalised* (snapshot at posting time).
  This means renaming/recolouring an account does not invalidate historical lines.
- source_type + source_id give FK-less polymorphic back-references so the ledger
  can be linked to invoices, payments, expenses, assets, payroll runs, etc.
- UniqueConstraint(org_id, source_type, source_id) on JournalEntry lets the
  backfill endpoint be idempotent — posting the same source twice is a no-op.
"""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
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


class AccountType(str, enum.Enum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"


class ChartOfAccount(Base):
    __tablename__ = "chart_of_accounts"
    __table_args__ = (
        UniqueConstraint("org_id", "code", name="uq_coa_org_code"),
        Index("ix_coa_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(
        Enum(AccountType, name="account_type_enum"), nullable=False
    )
    account_subtype: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    entries_as_lines: Mapped[list[JournalLine]] = relationship(
        "JournalLine",
        primaryjoin="foreign(JournalLine.account_code) == ChartOfAccount.code",
        viewonly=True,
    )


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "source_type", "source_id",
            name="uq_journal_entry_source",
        ),
        Index("ix_journal_entry_org_date", "org_id", "entry_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    entry_date: Mapped[Date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_posted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    lines: Mapped[list[JournalLine]] = relationship(
        "JournalLine", back_populates="entry", cascade="all, delete-orphan"
    )


class JournalLine(Base):
    __tablename__ = "journal_lines"
    __table_args__ = (
        Index("ix_journal_lines_entry_id", "journal_entry_id"),
        Index("ix_journal_lines_account_code", "account_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_code: Mapped[str] = mapped_column(String(10), nullable=False)
    debit: Mapped[Numeric] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    credit: Mapped[Numeric] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    memo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="SEK", nullable=False)

    entry: Mapped[JournalEntry] = relationship("JournalEntry", back_populates="lines")
