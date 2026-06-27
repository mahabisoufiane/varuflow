"""Subscription grace-period model (v106).

Tracks payment-failure grace windows so orgs are not immediately
downgraded when a Stripe invoice payment fails.  A grace period gives
the customer 7 days to update their payment method before the system
auto-downgrades their plan to FREE.
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GracePeriodStatus(str, PyEnum):
    ACTIVE = "active"
    RECOVERED = "recovered"
    EXPIRED = "expired"


class SubscriptionGracePeriod(Base):
    __tablename__ = "subscription_grace_periods"

    id: Mapped[uuid.UUID] = mapped_column(
        default=uuid.uuid4, primary_key=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    failed_invoice_id: Mapped[str | None] = mapped_column(String(255))
    failed_amount_cents: Mapped[int | None] = mapped_column(Integer)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[GracePeriodStatus] = mapped_column(
        Enum(GracePeriodStatus, name="grace_period_status"),
        default=GracePeriodStatus.ACTIVE,
        nullable=False,
    )
    recovered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    expired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    notification_sent_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    last_notification_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    org = relationship("Organization", lazy="selectin")
