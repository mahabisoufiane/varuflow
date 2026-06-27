from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True,
                                     server_default=func.gen_random_uuid())
    org_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True),
                                         ForeignKey("organizations.id", ondelete="CASCADE"),
                                         nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    company: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="new")
    assigned_to: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True),
                                                         ForeignKey("staff.id", ondelete="SET NULL"),
                                                         nullable=True, index=True)
    score: Mapped[int] = mapped_column(Integer(), nullable=False, server_default="0")
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    lead_form_submission_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("lead_form_submissions.id", ondelete="SET NULL"),
        nullable=True,
    )
    converted_customer_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
    )
    converted_deal_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("deals.id", ondelete="SET NULL"),
        nullable=True,
    )
    converted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_contacted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  server_default=func.now(), nullable=False)

    score_events: Mapped[List["LeadScoreEvent"]] = relationship(
        "LeadScoreEvent", back_populates="lead", cascade="all, delete-orphan",
        order_by="LeadScoreEvent.created_at",
    )


class LeadScoreEvent(Base):
    __tablename__ = "lead_score_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True,
                                     server_default=func.gen_random_uuid())
    lead_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True),
                                           ForeignKey("leads.id", ondelete="CASCADE"),
                                           nullable=False, index=True)
    org_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True),
                                          ForeignKey("organizations.id", ondelete="CASCADE"),
                                          nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    points: Mapped[int] = mapped_column(Integer(), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  server_default=func.now(), nullable=False)

    lead: Mapped["Lead"] = relationship("Lead", back_populates="score_events")
