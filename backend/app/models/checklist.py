"""Checklist — templates, template items, runs and run items."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ChecklistTemplate(Base):
    __tablename__ = "checklist_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    # daily | weekly | monthly | manual
    frequency: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    items: Mapped[list["ChecklistTemplateItem"]] = relationship(
        "ChecklistTemplateItem", back_populates="template", cascade="all, delete-orphan"
    )
    runs: Mapped[list["ChecklistRun"]] = relationship(
        "ChecklistRun", back_populates="template", cascade="all, delete-orphan"
    )


class ChecklistTemplateItem(Base):
    __tablename__ = "checklist_template_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checklist_templates.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    template: Mapped[ChecklistTemplate] = relationship(
        "ChecklistTemplate", back_populates="items"
    )


class ChecklistRun(Base):
    __tablename__ = "checklist_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checklist_templates.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    started_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # in_progress | completed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    template: Mapped[ChecklistTemplate] = relationship(
        "ChecklistTemplate", back_populates="runs"
    )
    items: Mapped[list["ChecklistRunItem"]] = relationship(
        "ChecklistRunItem", back_populates="run", cascade="all, delete-orphan"
    )


class ChecklistRunItem(Base):
    __tablename__ = "checklist_run_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checklist_runs.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    template_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("checklist_template_items.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    is_checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    checked_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)

    run: Mapped[ChecklistRun] = relationship("ChecklistRun", back_populates="items")
    template_item: Mapped[ChecklistTemplateItem] = relationship("ChecklistTemplateItem")
