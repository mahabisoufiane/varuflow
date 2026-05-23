"""bi1 business intelligence — dashboards, report builder, scheduled reports, benchmarks

Revision ID: c6w7x8y9z0a1
Revises: b5v6w7x8y9z0
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "c6w7x8y9z0a1"
down_revision = "b5v6w7x8y9z0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add industry sector to organizations (used for benchmark comparisons)
    op.add_column(
        "organizations",
        sa.Column("industry_sector", sa.String(50), nullable=True),
    )

    # Custom dashboard layouts per user/org
    op.create_table(
        "dashboard_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("layout", JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_dashboard_configs_org_id", "dashboard_configs", ["org_id"])
    op.create_index("ix_dashboard_configs_user_id", "dashboard_configs", ["user_id"])

    # Saved custom report definitions
    op.create_table(
        "custom_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("config", JSONB, nullable=False, server_default="{}"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_row_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_custom_reports_org_id", "custom_reports", ["org_id"])

    # Scheduled email delivery of reports
    op.create_table(
        "scheduled_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("report_type", sa.String(30), nullable=False),  # analytics_overview | pnl | custom
        sa.Column("custom_report_id", sa.String(36), nullable=True),  # FK to custom_reports if type=custom
        sa.Column("config", JSONB, nullable=False, server_default="{}"),
        sa.Column("recipients", JSONB, nullable=False, server_default="[]"),  # [{"email": "...", "name": "..."}]
        sa.Column("cron_expr", sa.String(50), nullable=False),  # e.g. "0 8 * * 1" = Mon 8am
        sa.Column("timezone", sa.String(50), nullable=False, server_default="'UTC'"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_send_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_scheduled_reports_org_id", "scheduled_reports", ["org_id"])
    op.create_index("ix_scheduled_reports_next_send", "scheduled_reports", ["next_send_at", "is_active"])


def downgrade() -> None:
    op.drop_table("scheduled_reports")
    op.drop_table("custom_reports")
    op.drop_table("dashboard_configs")
    op.drop_column("organizations", "industry_sector")
