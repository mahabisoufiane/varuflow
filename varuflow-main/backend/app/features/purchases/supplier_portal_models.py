"""SQLAlchemy model for the supplier portal token (Item 37, v52).

One row per magic-link token a supplier has been given. Raw tokens are
never persisted — only their SHA-256 hash. The ``is_revoked`` flag and
``expires_at`` together make a token cheap to invalidate without
touching the Redis cache layer.
"""
from __future__ import annotations

from typing import Optional

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SupplierPortalToken(Base):
    __tablename__ = "supplier_portal_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    # SHA-256 hex of the raw token delivered via magic link.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    is_revoked: Mapped[bool] = mapped_column(
        Boolean, server_default="false", default=False, nullable=False,
    )

    supplier = relationship("Supplier", foreign_keys=[supplier_id])
