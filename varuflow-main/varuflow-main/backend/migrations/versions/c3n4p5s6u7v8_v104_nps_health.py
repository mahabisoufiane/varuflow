"""v104 – nps_surveys + subscription_health_scores tables

Revision ID: c3n4p5s6u7v8
Revises: b2o3p4r5e6f7
Create Date: 2026-05-02
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c3n4p5s6u7v8"
down_revision = "b2o3p4r5e6f7"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # nps_surveys
    op.create_table(
        "nps_surveys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("score", sa.Integer, nullable=True),   # NULL until responded
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("survey_type", sa.String(30), nullable=False),  # day_30 | day_90 | feature_specific | cancellation | quarterly
        sa.Column("triggered_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_time_seconds", sa.Integer, nullable=True),
        sa.Column("followup_status", sa.String(20), nullable=False, server_default="none"),  # none|csm_assigned|churned
    )
    op.create_index("ix_nps_org_id", "nps_surveys", ["org_id"])
    op.create_index("ix_nps_user_id", "nps_surveys", ["user_id"])
    op.create_index("ix_nps_type", "nps_surveys", ["survey_type"])
    op.create_index("ix_nps_responded_at", "nps_surveys", ["responded_at"])

    # subscription_health_scores
    op.create_table(
        "subscription_health_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),  # healthy|at_risk|critical
        sa.Column("factors", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("intervention_triggered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_shs_org_id", "subscription_health_scores", ["org_id"])
    op.create_index("ix_shs_risk_level", "subscription_health_scores", ["risk_level"])
    op.create_index("ix_shs_calculated_at", "subscription_health_scores", ["calculated_at"])

def downgrade() -> None:
    op.drop_index("ix_shs_calculated_at", "subscription_health_scores")
    op.drop_index("ix_shs_risk_level", "subscription_health_scores")
    op.drop_index("ix_shs_org_id", "subscription_health_scores")
    op.drop_table("subscription_health_scores")
    op.drop_index("ix_nps_responded_at", "nps_surveys")
    op.drop_index("ix_nps_type", "nps_surveys")
    op.drop_index("ix_nps_user_id", "nps_surveys")
    op.drop_index("ix_nps_org_id", "nps_surveys")
    op.drop_table("nps_surveys")
