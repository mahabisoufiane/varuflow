"""Payroll processing models.

Tables:
  payroll_runs    — a payroll batch for one period (DRAFT → APPROVED → PAID)
  payroll_entries — one row per employee per run with gross/net/tax breakdown
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
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.services.encryption import EncryptedString


class PayrollRun(Base):
    __tablename__ = "payroll_runs"
    __table_args__ = (
        Index("ix_payroll_runs_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    period_start: Mapped[Date] = mapped_column(Date, nullable=False)
    period_end: Mapped[Date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)  # DRAFT|APPROVED|PAID
    total_gross: Mapped[Numeric] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    total_employer_cost: Mapped[Numeric] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    approved_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    entries: Mapped[list[PayrollEntry]] = relationship(
        "PayrollEntry", back_populates="run", cascade="all, delete-orphan"
    )


class PayrollEntry(Base):
    __tablename__ = "payroll_entries"
    __table_args__ = (
        Index("ix_payroll_entries_run_id", "payroll_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payroll_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False
    )
    staff_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    employee_name: Mapped[str] = mapped_column(String(200), nullable=False)
    personal_number: Mapped[str | None] = mapped_column(EncryptedString(64), nullable=True)
    gross_salary: Mapped[Numeric] = mapped_column(Numeric(14, 2), nullable=False)
    income_tax: Mapped[Numeric] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    social_contribution: Mapped[Numeric] = mapped_column(Numeric(14, 2), default=Decimal("0"), nullable=False)
    net_salary: Mapped[Numeric] = mapped_column(Numeric(14, 2), nullable=False)
    employer_total: Mapped[Numeric] = mapped_column(Numeric(14, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    run: Mapped[PayrollRun] = relationship("PayrollRun", back_populates="entries")
