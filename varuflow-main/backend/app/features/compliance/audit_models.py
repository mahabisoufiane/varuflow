from __future__ import annotations

from typing import Optional

import uuid

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLogEntry(Base):
    """Append-only log of sensitive actions (GDPR delete, plan change,
    invoice write-off, team role change, etc.).

    Rows are never updated or deleted from application code. Retention is
    handled at the DB layer — keep for 7 years per bokföringslagen when
    `target_type` is billing-related.
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        index=True,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(64))
    target_id: Mapped[str | None] = mapped_column(String(128))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    extra: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    # ── Tamper-evident hash chain (SOC 2) ────────────────────────────────────
    # services/audit_chain.py implements verification over these three columns;
    # the columns themselves were never added when that service shipped, so the
    # /api/compliance/audit-chain endpoints 500'd on first call. sequence_no is
    # a DB-side identity for stable global ordering; hashes default to the
    # genesis value for legacy rows (verify treats genesis rows as unchained).
    sequence_no: Mapped[int] = mapped_column(
        BigInteger, Identity(always=False), nullable=False, unique=True
    )
    previous_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="0" * 64
    )
    row_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="0" * 64
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
