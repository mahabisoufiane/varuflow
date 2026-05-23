"""SQLAlchemy model for custom invoice templates (Item 42, v56)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InvoiceTemplate(Base):
    """Per-org invoice template.

    A tenant may have many templates (e.g. "Retail client default",
    "Internal projects") but only one can carry ``is_default=True``
    at a time — enforced via a partial unique index in migration v56.
    ``is_active=False`` retires a template without breaking any
    historical attachment.
    """

    __tablename__ = "invoice_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
    )
    logo_url: Mapped[str | None] = mapped_column(
        String(1024), nullable=True,
    )
    primary_color: Mapped[str] = mapped_column(
        String(7), nullable=False, default="#1a2332",
    )
    accent_color: Mapped[str] = mapped_column(
        String(7), nullable=False, default="#2563eb",
    )
    font_family: Mapped[str] = mapped_column(
        String(60), nullable=False, default="Helvetica",
    )
    show_bank_details: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
    )
    show_qr_code: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
    )
    footer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    header_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
