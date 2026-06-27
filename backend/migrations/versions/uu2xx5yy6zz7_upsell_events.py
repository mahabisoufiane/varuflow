"""Add upsell_events table for upsell trigger tracking.

Revision ID: uu2xx5yy6zz7
Revises:     qq7rr8ss9tt0
Create Date: 2026-05-02
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision    = "uu2xx5yy6zz7"
down_revision = "qq7rr8ss9tt0"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.create_table(
        "upsell_events",
        sa.Column("id",           postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id",       postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id",      postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trigger_id",   sa.String(80),  nullable=False),
        sa.Column("placement",    sa.String(20),  nullable=False, server_default="modal"),
        sa.Column("target_tier",  sa.String(20),  nullable=False, server_default="PRO"),
        sa.Column("ab_variant",   sa.String(20),  nullable=True),
        sa.Column("shown_at",     sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("clicked_at",   sa.DateTime(timezone=True), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_upsell_events_org_id",    "upsell_events", ["org_id"])
    op.create_index("ix_upsell_events_user_id",   "upsell_events", ["user_id"])
    op.create_index("ix_upsell_events_trigger_id","upsell_events", ["trigger_id"])
    op.create_index(
        "ix_upsell_events_user_shown",
        "upsell_events",
        ["user_id", "shown_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_upsell_events_user_shown",  table_name="upsell_events")
    op.drop_index("ix_upsell_events_trigger_id",  table_name="upsell_events")
    op.drop_index("ix_upsell_events_user_id",     table_name="upsell_events")
    op.drop_index("ix_upsell_events_org_id",      table_name="upsell_events")
    op.drop_table("upsell_events")
