"""Recurring Reminders — scheduled reminders with occurrence tracking."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RecurringReminder(Base):
    __tablename__ = "recurring_reminders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    # daily | weekly | monthly | custom
    frequency: Mapped[str] = mapped_column(String(20), nullable=False, default="weekly")
    # 0=Mon, 6=Sun — required for weekly
    day_of_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 1-31 — required for monthly
    day_of_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # "HH:MM"
    time_of_day: Mapped[str] = mapped_column(String(8), nullable=False, default="09:00")
    assigned_to_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    occurrences: Mapped[list["ReminderOccurrence"]] = relationship(
        "ReminderOccurrence", back_populates="reminder", cascade="all, delete-orphan"
    )


class ReminderOccurrence(Base):
    __tablename__ = "reminder_occurrences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reminder_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recurring_reminders.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # pending | completed | snoozed | dismissed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    reminder: Mapped[RecurringReminder] = relationship(
        "RecurringReminder", back_populates="occurrences"
    )
