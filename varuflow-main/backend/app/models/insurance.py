from __future__ import annotations

"""Insurance policy and claim models."""

import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Text, Date, DateTime, Numeric, Integer, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InsurancePolicy(Base):
    """Insurance policy held by an organisation."""

    __tablename__ = "insurance_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    policy_name: Mapped[str] = mapped_column(String(200), nullable=False)
    insurer: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    policy_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    coverage_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="SEK")
    premium_annual: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    renewal_due: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    renewal_reminder_days: Mapped[int] = mapped_column(Integer(), nullable=False, default=30)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class InsuranceClaim(Base):
    """Claim filed against an insurance policy."""

    __tablename__ = "insurance_claims"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("insurance_policies.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_date: Mapped[date] = mapped_column(Date(), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    amount_claimed: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    amount_settled: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    settled_at: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
