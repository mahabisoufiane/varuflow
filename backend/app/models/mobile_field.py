import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Any
from sqlalchemy import String, Text, Boolean, Date, DateTime, Integer, Numeric, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class DeliveryRoute(Base):
    """GPS delivery/field service route with ordered stops."""
    __tablename__ = "delivery_routes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    driver_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    route_date: Mapped[date] = mapped_column(Date(), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    total_km: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    notification_threshold_minutes: Mapped[int] = mapped_column(Integer(), nullable=False, default=15)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class RouteStop(Base):
    """Individual stop within a delivery/field route."""
    __tablename__ = "route_stops"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("delivery_routes.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    stop_type: Mapped[str] = mapped_column(String(20), nullable=False)
    ref_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    lat: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6), nullable=True)
    lng: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    # pending / visited / completed / skipped / exception
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    arrived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Delivery exception fields
    exception_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    exception_reason: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    reschedule_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    # Proof of delivery
    pod_photo_url: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    pod_signature_data: Mapped[Optional[Any]] = mapped_column(JSONB(), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DigitalSignature(Base):
    """SVG signature capture for delivery notes, contracts, invoices."""
    __tablename__ = "digital_signatures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    signer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    signer_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    ref_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    svg_data: Mapped[str] = mapped_column(Text(), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StripeTerminalSession(Base):
    """Stripe Terminal tap-to-pay session (NFC / chip)."""
    __tablename__ = "stripe_terminal_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    reader_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    payment_intent_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="SEK")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="initiated")
    stripe_response: Mapped[Optional[Any]] = mapped_column(JSONB(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class VoiceNote(Base):
    """Audio voice note attached to a customer, supplier, or route stop."""
    __tablename__ = "voice_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    file_url: Mapped[str] = mapped_column(Text(), nullable=False)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    transcription: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
