from __future__ import annotations

"""RegulatoryEvent — compliance deadline/calendar entry."""

import uuid
from datetime import datetime, date
from typing import Optional

from sqlalchemy import String, Text, Date, DateTime, Integer, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RegulatoryEvent(Base):
    """Compliance deadline or calendar entry for a regulatory obligation."""

    __tablename__ = "regulatory_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    # vat_filing/annual_report/tax_payment/payroll_submission/audit/license_renewal/other
    country: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    due_date: Mapped[date] = mapped_column(Date(), nullable=False, index=True)
    recurrence: Mapped[str] = mapped_column(String(20), nullable=False, default="once")
    # once/monthly/quarterly/annually
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="upcoming")
    # upcoming/completed/overdue/waived
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    alert_days: Mapped[int] = mapped_column(Integer(), nullable=False, default=14)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
