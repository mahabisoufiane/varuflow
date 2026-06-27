"""hr4 — time_entries

Revision ID: o4j5k6l7m8n9
Revises:     n3i4j5k6l7m8
Create Date: 2026-04-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "o4j5k6l7m8n9"
down_revision = "n3i4j5k6l7m8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "time_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_date", sa.Date, nullable=False),
        sa.Column("project", sa.String(200), nullable=False),
        sa.Column("client", sa.String(200), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("hours", sa.Numeric(5, 2), nullable=False),
        sa.Column("billable", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("hourly_rate", sa.Numeric(10, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_time_entries_org_id", "time_entries", ["org_id"])
    op.create_index("ix_time_entries_staff_id", "time_entries", ["staff_id"])
    op.create_index("ix_time_entries_entry_date", "time_entries", ["entry_date"])


def downgrade() -> None:
    op.drop_table("time_entries")
