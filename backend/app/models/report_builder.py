"""Report builder: saved no-code report definitions and scheduled delivery."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SavedReport(Base):
    __tablename__ = "saved_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Entity to query: "customers" | "invoices" | "products" | "expenses" | etc.
    entity: Mapped[str] = mapped_column(String(64), nullable=False)
    # [{field, operator, value}]
    filters: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    # ["customer_id", "month"] etc.
    group_by: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    # [{column, func}]  func = count|sum|avg|min|max
    aggregates: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    # Column names to show in output
    columns: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    sort_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    sort_dir: Mapped[str] = mapped_column(String(4), nullable=False, server_default="asc")
    # "bar" | "line" | "pie" | null
    chart_type: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    is_shared: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class RbScheduledReport(Base):
    __tablename__ = "report_builder_schedules"  # canonical scheduled_reports in bi.py

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    recipient_emails: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    cron_expression: Mapped[str] = mapped_column(String(64), nullable=False)
    export_format: Mapped[str] = mapped_column(String(8), nullable=False, server_default="csv")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    last_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
