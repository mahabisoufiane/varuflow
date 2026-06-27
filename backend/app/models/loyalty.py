"""Loyalty program ORM models (v51 — Item 35).

Three tables:

* :class:`LoyaltyProgram` — per-org config (points rate, redemption
  value, expiry window). One active row per org is the norm.
* :class:`LoyaltyAccount` — per-customer balance & tier cache.
  Tier is denormalised for fast display; recompute in the engine.
* :class:`LoyaltyTransaction` — signed ledger rows (earn / redeem /
  expire / adjust). Positive = credit, negative = debit. Balance on
  the account must always equal ``SUM(points)`` over non-expired rows.
"""
from __future__ import annotations

from typing import Optional

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LoyaltyProgram(Base):
    __tablename__ = "loyalty_programs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="Loyalty")
    # Points earned per 1.0 of transaction value (in the transaction's
    # currency). A ``Decimal`` so orgs can offer e.g. 0.5 pts/SEK.
    points_per_currency_unit: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=Decimal("1")
    )
    # Currency value of one point when redeemed (0.01 = 1 öre per point).
    redemption_rate: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0.01")
    )
    expiry_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.utcnow()
    )


class LoyaltyAccount(Base):
    __tablename__ = "loyalty_accounts"
    __table_args__ = (
        UniqueConstraint("org_id", "customer_id", name="uq_loyalty_accounts_org_customer"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    points_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lifetime_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Denormalised tier cache: bronze | silver | gold | platinum.
    tier: Mapped[str] = mapped_column(String(32), nullable=False, default="bronze")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.utcnow()
    )


class LoyaltyTransaction(Base):
    __tablename__ = "loyalty_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("loyalty_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Signed. Earn / adjust-up = positive; redeem / expire / adjust-down = negative.
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    # One of: ``earn``, ``redeem``, ``expire``, ``adjust``.
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.utcnow()
    )
