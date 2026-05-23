"""ORM model for operator-to-operator referrals."""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class OperatorReferral(Base):
    __tablename__ = "operator_referrals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    referrer_org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    referrer_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    referee_org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    referral_code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    referral_method: Mapped[str] = mapped_column(String(20), nullable=False, default="link")
    reward_type: Mapped[str] = mapped_column(String(20), nullable=False, default="commission")
    commission_rate_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("20"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signed_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    months_remaining: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    subscription_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    commission_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    stripe_coupon_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    stripe_payout_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    referrer_email_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Valid statuses
    STATUS_PENDING = "pending"
    STATUS_SIGNED_UP = "signed_up"
    STATUS_CONVERTED = "converted"
    STATUS_PAID_OUT = "paid_out"
    STATUS_EXPIRED = "expired"

    # Reward types
    REWARD_COMMISSION = "commission"
    REWARD_FREE_MONTH = "free_month"
