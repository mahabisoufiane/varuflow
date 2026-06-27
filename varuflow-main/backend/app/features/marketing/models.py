"""SQLAlchemy models for email campaigns (Item 40, v55)."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CampaignStatus(str, enum.Enum):
    DRAFT = "DRAFT"          # editable, never sent
    SCHEDULED = "SCHEDULED"  # has scheduled_at, picked up by the dispatch sweep
    SENT = "SENT"            # recipients written, sent_at populated


class CampaignSendStatus(str, enum.Enum):
    SENT = "SENT"         # Resend returned 2xx
    FAILED = "FAILED"     # transport error (retry not implemented in v55)
    BOUNCED = "BOUNCED"   # provider async bounce webhook
    OPENED = "OPENED"     # pixel beacon (or provider tracking webhook)


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    # Structured block editor document (Item 63). Optional — legacy
    # campaigns predate the block editor; body_html remains canonical.
    blocks: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Nullable FK. A campaign can target a since-deleted segment — the
    # audit trail still shows the send history and recipient_count.
    segment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("segments.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus, name="campaign_status"),
        nullable=False,
        default=CampaignStatus.DRAFT,
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    recipient_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    sends: Mapped[list["CampaignSend"]] = relationship(
        "CampaignSend",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )


class CampaignSend(Base):
    __tablename__ = "campaign_sends"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id", "customer_id",
            name="uq_campaign_sends_campaign_customer",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Denormalised email — preserves the delivery address even if the
    # customer later updates their email. Required for GDPR Article 30
    # "record of processing" evidence.
    email: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[CampaignSendStatus] = mapped_column(
        Enum(CampaignSendStatus, name="campaign_send_status"),
        nullable=False,
        default=CampaignSendStatus.SENT,
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    campaign: Mapped["Campaign"] = relationship(
        "Campaign", back_populates="sends",
    )
