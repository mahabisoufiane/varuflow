"""dashboard builder: create dashboard_layouts and scheduled_dashboards tables

Revision ID: hh8ii9jj0kk1
Revises: ff6gg7hh8ii9
Create Date: 2026-05-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "hh8ii9jj0kk1"
down_revision = "ff6gg7hh8ii9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dashboard_layouts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("widgets", JSONB(), nullable=False, server_default="[]"),
        sa.Column("date_range", sa.String(32), nullable=False, server_default="this_month"),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("shared_role", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_dashboard_layouts_org_id", "dashboard_layouts", ["org_id"])
    op.create_index("ix_dashboard_layouts_user_id", "dashboard_layouts", ["user_id"])

    op.create_table(
        "scheduled_dashboards",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), nullable=False),
        sa.Column("layout_id", UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_emails", JSONB(), nullable=False, server_default="[]"),
        sa.Column("cron_expression", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_scheduled_dashboards_org_id", "scheduled_dashboards", ["org_id"])


def downgrade() -> None:
    op.drop_table("scheduled_dashboards")
    op.drop_table("dashboard_layouts")
