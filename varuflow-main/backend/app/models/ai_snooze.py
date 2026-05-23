"""Persistent snooze rows for AI action cards (v18).

A snooze suppresses a card with the same (card_type, product_id) for the
caller's org until ``snoozed_until``. Unique on (org_id, card_type,
product_id) so re-snoozing the same card UPSERTs the new expiry.
"""
from __future__ import annotations

from typing import Optional

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AiCardSnooze(Base):
    __tablename__ = "ai_card_snooze"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "card_type", "product_id",
            name="uq_ai_card_snooze_org_card_product",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    card_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # Nullable: some card types (e.g. customer churn) don't tie to a product.
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=True,
    )
    snoozed_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
