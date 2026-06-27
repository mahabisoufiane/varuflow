"""Auto-reorder run audit trail (v38 — Item 16).

Every invocation of the auto-reorder service writes one row here whether
the run succeeds, fails, or finds nothing to do. The list is surfaced on
Settings → Auto-reorder as the owner's run history, and analytics
consumes it for the "runs in last 30 days" KPI.

We keep this separate from AuditLogEntry because the audit log is an
append-only forensic trail of *sensitive* actions (GDPR, billing, role
changes). Auto-reorder runs are high-volume operational telemetry —
mixing them into the audit log would bury real signals.
"""
from __future__ import annotations

from typing import Optional

import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AutoReorderRun(Base):
    __tablename__ = "auto_reorder_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # "scheduler" | "manual" | "api" — free-form string rather than an
    # enum so future trigger sources (webhook, integration) don't
    # require a schema migration.
    triggered_by: Mapped[str] = mapped_column(
        String(32), server_default="scheduler", default="scheduler", nullable=False
    )
    run_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    products_checked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    purchase_orders_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    products_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # "completed" | "failed" | "partial" — see AutoReorderResult for the
    # rules that determine which value is written.
    status: Mapped[str] = mapped_column(
        String(16), server_default="completed", default="completed", nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
