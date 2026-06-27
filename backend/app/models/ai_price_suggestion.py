"""AiPriceSuggestion model — Sprint 13: Reporting + AI Across the Stack."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AiPriceSuggestion(Base):
    __tablename__ = "ai_price_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cost_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    target_margin_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    current_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    suggested_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_used: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="gpt-4o"
    )
    accepted: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    accepted_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
