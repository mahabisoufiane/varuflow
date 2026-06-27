"""crm1 — deals and deal_activities tables

Revision ID: h7c8d9e0f1g2
Revises:     g6b7c8d9e0f1
Create Date: 2026-04-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "h7c8d9e0f1g2"
down_revision = "g6b7c8d9e0f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("stage", sa.String(30), nullable=False, server_default="prospect"),
        sa.Column("value", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("close_date", sa.Date, nullable=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("probability", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_deals_org_id", "deals", ["org_id"])
    op.create_index("ix_deals_stage", "deals", ["stage"])
    op.create_index("ix_deals_close_date", "deals", ["close_date"])

    op.create_table(
        "deal_activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activity_type", sa.String(20), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("actor_name", sa.String(255), nullable=True),
        sa.Column("old_value", sa.String(100), nullable=True),
        sa.Column("new_value", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_deal_activities_deal_id", "deal_activities", ["deal_id"])
    op.create_index("ix_deal_activities_org_id", "deal_activities", ["org_id"])


def downgrade() -> None:
    op.drop_table("deal_activities")
    op.drop_table("deals")
