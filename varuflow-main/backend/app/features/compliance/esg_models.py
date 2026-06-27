from __future__ import annotations

"""EsgReport — consolidated ESG report."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Text, Boolean, DateTime, Numeric, Integer, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EsgReport(Base):
    """Consolidated Environmental, Social, and Governance report for an organisation."""

    __tablename__ = "esg_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    report_year: Mapped[int] = mapped_column(Integer(), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # draft/published
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Environmental
    total_co2_tonnes: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    co2_per_revenue: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 6), nullable=True)
    renewable_energy_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    waste_recycled_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)

    # Social
    employee_count: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    female_leadership_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    training_hours_per_employee: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    employee_satisfaction_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 2), nullable=True)
    injury_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)

    # Governance
    audit_complete: Mapped[Optional[bool]] = mapped_column(Boolean(), nullable=True)
    whistleblower_mechanism: Mapped[Optional[bool]] = mapped_column(Boolean(), nullable=True)
    anti_corruption_training_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    board_diversity_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
