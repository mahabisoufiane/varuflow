from __future__ import annotations

"""CarbonEntry — GHG emissions tracker (Scope 1/2/3)."""

import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Boolean, Date, DateTime, Numeric, Integer, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CarbonEntry(Base):
    """Greenhouse gas emissions entry covering Scope 1, 2, and 3."""

    __tablename__ = "carbon_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    scope: Mapped[int] = mapped_column(Integer(), nullable=False)
    # 1=direct combustion, 2=purchased electricity, 3=supply chain & other indirect
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    emission_factor: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 6), nullable=True)
    co2_kg: Mapped[Decimal] = mapped_column(Numeric(16, 4), nullable=False)
    period_start: Mapped[date] = mapped_column(Date(), nullable=False, index=True)
    period_end: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    data_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
