"""ImportJob model — tracks CSV/XLSX data migration jobs."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    import_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    filename: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_system: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    total_rows: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    imported_rows: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    failed_rows: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    column_mapping: Mapped[Optional[Any]] = mapped_column(JSONB(), nullable=True)
    validation_errors: Mapped[Optional[Any]] = mapped_column(JSONB(), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
