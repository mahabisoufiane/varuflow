from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class BirthdayVoucher(Base):
    __tablename__ = "birthday_vouchers"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    voucher_code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    discount_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pct")
    discount_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    valid_from: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    is_redeemed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    redeemed_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)
    generated_for_year: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
