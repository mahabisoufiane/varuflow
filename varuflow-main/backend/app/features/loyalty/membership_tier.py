from __future__ import annotations
from sqlalchemy import String, Text, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
import datetime, uuid
from app.database import Base

class MembershipTier(Base):
    __tablename__ = "membership_tiers"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    min_points: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    card_color: Mapped[str] = mapped_column(String(7), nullable=False, server_default="#CD7F32")
    card_text_color: Mapped[str] = mapped_column(String(7), nullable=False, server_default="#FFFFFF")
    benefits: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

class CustomerMembership(Base):
    __tablename__ = "customer_memberships"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("membership_tiers.id", ondelete="SET NULL"), nullable=True)
    awarded_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    valid_until: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    __table_args__ = (UniqueConstraint("org_id", "customer_id", name="uq_customer_memberships_org_customer"),)
