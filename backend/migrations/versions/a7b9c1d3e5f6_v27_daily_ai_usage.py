"""v27: daily_ai_usage counter

Revision ID: a7b9c1d3e5f6
Revises: f6a8c0e2d4b5
Create Date: 2026-04-23

Tracks per-(org, date) AI chat message counts for daily rate limiting.
One row per org per UTC date; UPSERT increments the counter atomically.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a7b9c1d3e5f6"
down_revision = "f6a8c0e2d4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_ai_usage",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # UTC calendar date. We use date (not timestamp) so the reset
        # window is midnight UTC for every tenant — predictable across
        # timezones and matches the scheduler's UTC-based dedupe keys.
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "org_id", "usage_date", name="uq_daily_ai_usage_org_date"
        ),
    )
    op.create_index(
        "ix_daily_ai_usage_org_date",
        "daily_ai_usage",
        ["org_id", "usage_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_daily_ai_usage_org_date", table_name="daily_ai_usage")
    op.drop_table("daily_ai_usage")
