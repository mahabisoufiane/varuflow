"""OKR — Objectives and Key Results with 3-level hierarchy.

Levels: company → department → individual
Each objective can have many key results that define measurable progress.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OkrObjective(Base):
    __tablename__ = "okr_objectives"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("okr_objectives.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    owner_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    # company | department | individual
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="company")
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # active | completed | cancelled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    period_label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    period_start: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    period_end: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    progress_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0")
    )
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    key_results: Mapped[list["OkrKeyResult"]] = relationship(
        "OkrKeyResult", back_populates="objective", cascade="all, delete-orphan"
    )
    children: Mapped[list["OkrObjective"]] = relationship(
        "OkrObjective",
        primaryjoin="OkrObjective.parent_id == OkrObjective.id",
        foreign_keys="[OkrObjective.parent_id]",
        lazy="select",
    )


class OkrKeyResult(Base):
    __tablename__ = "okr_key_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    objective_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("okr_objectives.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    target_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    current_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0")
    )
    unit: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    # on_track | at_risk | off_track | completed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="on_track")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    objective: Mapped[OkrObjective] = relationship(
        "OkrObjective", back_populates="key_results"
    )
