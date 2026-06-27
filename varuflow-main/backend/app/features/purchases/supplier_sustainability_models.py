from __future__ import annotations

"""SupplierSustainabilityRating — ESG rating per supplier."""

import uuid
from datetime import datetime, date
from typing import Optional

from sqlalchemy import String, Text, Boolean, Date, DateTime, Integer, ForeignKey, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SupplierSustainabilityRating(Base):
    """ESG sustainability rating attached to a specific supplier."""

    __tablename__ = "supplier_sustainability_ratings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True)
    environmental_score: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    social_score: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    governance_score: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    overall_score: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    certifications: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ethical_sourcing_verified: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    last_audit_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    next_audit_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    audit_notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    # low/medium/high/critical
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "supplier_id", name="uq_supplier_sustainability_org_supplier"),
    )
