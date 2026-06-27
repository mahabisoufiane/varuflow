"""NPS — Net Promoter Score triggered surveys and subscription health scores."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NpsSurvey(Base):
    __tablename__ = "nps_surveys"

    # Survey type constants
    TYPE_DAY_30 = "day_30"
    TYPE_DAY_90 = "day_90"
    TYPE_CANCELLATION = "cancellation"
    TYPE_QUARTERLY = "quarterly"
    TYPE_FEATURE = "feature_specific"

    # Followup status constants
    FOLLOWUP_NONE = "none"
    FOLLOWUP_CSM = "csm_assigned"
    FOLLOWUP_CHURNED = "churned"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True,
    )
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    survey_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    responded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    response_time_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    followup_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="none"
    )


class SubscriptionHealthScore(Base):
    __tablename__ = "subscription_health_scores"

    # Risk level constants
    RISK_HEALTHY = "healthy"
    RISK_AT_RISK = "at_risk"
    RISK_CRITICAL = "critical"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    factors: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    intervention_triggered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
