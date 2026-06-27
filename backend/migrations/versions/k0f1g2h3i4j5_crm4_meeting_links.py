"""crm4 — meeting_links table

Revision ID: k0f1g2h3i4j5
Revises:     j9e0f1g2h3i4
Create Date: 2026-04-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "k0f1g2h3i4j5"
down_revision = "j9e0f1g2h3i4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meeting_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True),
        sa.Column("slug", sa.String(80), unique=True, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("duration_minutes", sa.Integer, nullable=False, server_default="30"),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("buffer_minutes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("min_notice_hours", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_meeting_links_org_id", "meeting_links", ["org_id"])
    op.create_index("ix_meeting_links_slug", "meeting_links", ["slug"])


def downgrade() -> None:
    op.drop_table("meeting_links")
