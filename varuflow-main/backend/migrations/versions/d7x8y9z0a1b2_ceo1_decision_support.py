"""ceo1 decision support — KPI goals, scenario planning

Revision ID: d7x8y9z0a1b2
Revises: c6w7x8y9z0a1
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "d7x8y9z0a1b2"
down_revision = "c6w7x8y9z0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # KPI goals — quantitative targets with a defined period
    op.create_table(
        "kpi_goals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("metric_key", sa.String(50), nullable=False),
        sa.Column("target_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("period_label", sa.String(50), nullable=False),   # e.g. "Q2 2026", "May 2026"
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_kpi_goals_org_id", "kpi_goals", ["org_id"])

    # Scenario plans — named what-if cash flow assumptions
    op.create_table(
        "scenarios",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("horizon_months", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("adjustments", JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_scenarios_org_id", "scenarios", ["org_id"])


def downgrade() -> None:
    op.drop_table("scenarios")
    op.drop_table("kpi_goals")
