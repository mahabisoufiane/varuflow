from __future__ import annotations

"""RiskItem — business risk register entry."""

import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Text, Date, DateTime, Numeric, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RiskItem(Base):
    """Business risk register entry."""

    __tablename__ = "risk_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    # supply_chain/key_person/currency/legal/operational/reputational/other
    description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    likelihood: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    # low/medium/high/critical
    impact: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    risk_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 1), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="identified")
    # identified/monitoring/mitigating/resolved/accepted
    mitigation_plan: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    owner_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    last_reviewed: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
