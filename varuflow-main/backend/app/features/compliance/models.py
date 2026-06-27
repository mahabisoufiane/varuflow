import uuid
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Text, Boolean, Date, DateTime, Integer, ForeignKey, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class FieldMaskingRule(Base):
    """Per-org role-based field masking rule."""
    __tablename__ = "field_masking_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    resource: Mapped[str] = mapped_column(String(50), nullable=False)
    field: Mapped[str] = mapped_column(String(50), nullable=False)
    mask_style: Mapped[str] = mapped_column(String(20), nullable=False, default="obfuscate")
    enabled: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "role", "resource", "field", name="uq_field_mask_rule"),
    )


class PentestReport(Base):
    """Penetration test report metadata (PDF stored in Supabase Storage)."""
    __tablename__ = "pentest_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    file_url: Mapped[str] = mapped_column(Text(), nullable=False)
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    test_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    tester_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    scope: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    findings_summary: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    critical_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    high_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    medium_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    low_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
