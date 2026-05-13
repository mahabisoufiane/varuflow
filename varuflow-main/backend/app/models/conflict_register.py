from __future__ import annotations

"""ConflictDeclaration — staff conflict of interest register."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Text, Boolean, DateTime, Numeric, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ConflictDeclaration(Base):
    """Staff declaration of a conflict of interest."""

    __tablename__ = "conflict_declarations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    declaration_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # supplier_relationship/customer_relationship/board_member/financial_interest/other
    counterparty_name: Mapped[str] = mapped_column(String(300), nullable=False)
    counterparty_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    relationship_description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    declared_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="SEK")
    is_reviewed: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # pending/approved/rejected
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
