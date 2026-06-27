import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ZatcaInvoice(Base):
    __tablename__ = "zatca_invoices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, unique=True)
    invoice_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    qr_tlv_b64: Mapped[str] = mapped_column(Text(), nullable=False)
    xml_content: Mapped[str] = mapped_column(Text(), nullable=False)
    clearance_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    clearance_response: Mapped[Optional[Any]] = mapped_column(JSONB(), nullable=True)
    zatca_uuid: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
