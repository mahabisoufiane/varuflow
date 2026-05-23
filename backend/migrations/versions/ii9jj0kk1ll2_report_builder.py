"""report builder: create saved_reports and scheduled_reports tables

Revision ID: ii9jj0kk1ll2
Revises: hh8ii9jj0kk1
Create Date: 2026-05-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "ii9jj0kk1ll2"
down_revision = "hh8ii9jj0kk1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("entity", sa.String(64), nullable=False),
        sa.Column("filters", JSONB(), nullable=False, server_default="[]"),
        sa.Column("group_by", JSONB(), nullable=False, server_default="[]"),
        sa.Column("aggregates", JSONB(), nullable=False, server_default="[]"),
        sa.Column("columns", JSONB(), nullable=False, server_default="[]"),
        sa.Column("sort_by", sa.String(128), nullable=True),
        sa.Column("sort_dir", sa.String(4), nullable=False, server_default="asc"),
        sa.Column("chart_type", sa.String(16), nullable=True),
        sa.Column("is_shared", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_saved_reports_org_id", "saved_reports", ["org_id"])
    op.create_index("ix_saved_reports_created_by", "saved_reports", ["created_by"])

    op.create_table(
        "scheduled_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), nullable=False),
        sa.Column("report_id", UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_emails", JSONB(), nullable=False, server_default="[]"),
        sa.Column("cron_expression", sa.String(64), nullable=False),
        sa.Column("export_format", sa.String(8), nullable=False, server_default="csv"),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_scheduled_reports_org_id", "scheduled_reports", ["org_id"])
    op.create_index("ix_scheduled_reports_report_id", "scheduled_reports", ["report_id"])


def downgrade() -> None:
    op.drop_table("scheduled_reports")
    op.drop_table("saved_reports")
