from __future__ import annotations
from sqlalchemy import String, Text, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
import datetime, uuid
from app.database import Base

class CustomerPreference(Base):
    __tablename__ = "customer_preferences"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    favorite_staff_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    preferred_time_of_day: Mapped[str | None] = mapped_column(String(20), nullable=True)
    preferred_day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    communication_channel: Mapped[str] = mapped_column(String(20), nullable=False, server_default="push")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    __table_args__ = (UniqueConstraint("org_id", "customer_id", name="uq_customer_preferences_org_customer"),)
