from __future__ import annotations
from sqlalchemy import String, Integer, Date, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
import datetime, uuid
from app.database import Base

class LoyaltyStreak(Base):
    __tablename__ = "loyalty_streaks"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    streak_type: Mapped[str] = mapped_column(String(30), nullable=False)
    current_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    longest_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_activity_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    streak_start_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    milestone_rewards: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    __table_args__ = (UniqueConstraint("org_id", "customer_id", "streak_type", name="uq_loyalty_streaks_org_customer_type"),)
