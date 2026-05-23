from __future__ import annotations
from sqlalchemy import String, Date, Boolean, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
import datetime, uuid
from app.database import Base

class CustomerImportantDate(Base):
    __tablename__ = "customer_important_dates"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    send_greeting: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    send_discount: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    discount_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_triggered_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    __table_args__ = (UniqueConstraint("org_id", "customer_id", "label", name="uq_customer_important_dates_org_customer_label"),)
