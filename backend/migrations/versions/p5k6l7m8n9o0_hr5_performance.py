"""hr5 — performance_cycles and performance_reviews

Revision ID: p5k6l7m8n9o0
Revises:     o4j5k6l7m8n9
Create Date: 2026-04-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "p5k6l7m8n9o0"
down_revision = "o4j5k6l7m8n9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "performance_cycles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_performance_cycles_org_id", "performance_cycles", ["org_id"])

    op.create_table(
        "performance_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cycle_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("performance_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_staff_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True),
        sa.Column("goals", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("self_assessment", sa.Text, nullable=True),
        sa.Column("manager_review", sa.Text, nullable=True),
        sa.Column("overall_rating", sa.Integer, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint("cycle_id", "staff_id", name="uq_perf_review_cycle_staff"),
    )
    op.create_index("ix_performance_reviews_org_id", "performance_reviews", ["org_id"])
    op.create_index("ix_performance_reviews_cycle_id", "performance_reviews", ["cycle_id"])
    op.create_index("ix_performance_reviews_staff_id", "performance_reviews", ["staff_id"])


def downgrade() -> None:
    op.drop_table("performance_reviews")
    op.drop_table("performance_cycles")
