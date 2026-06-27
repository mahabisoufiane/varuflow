"""Staff availability overrides (Item 57).

Complements [bookings.py](bookings.py) ``Staff.working_hours``
JSONB with per-date time-off, sick leave, extra shifts and
holidays. The booking slot resolver subtracts ``time_off``/``sick``/
``holiday`` rows from the baseline and adds ``extra_shift`` rows.
"""
from __future__ import annotations

from typing import Optional

import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StaffAvailabilityKind(str, enum.Enum):
    TIME_OFF = "time_off"
    SICK = "sick"
    EXTRA_SHIFT = "extra_shift"
    HOLIDAY = "holiday"


class StaffAvailabilityOverride(Base):
    __tablename__ = "staff_availability_overrides"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="ck_staff_availability_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staff.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
