"""Multi-entity roles, OKR tables, budget department workflow.

Revision ID: bb1cc2dd3ee4
Revises:     aa1bb2cc3dd4
Create Date: 2026-05-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "bb1cc2dd3ee4"
down_revision = "aa1bb2cc3dd4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── multi_entity_roles ─────────────────────────────────────────────────────
    op.create_table(
        "multi_entity_roles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("granted_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("user_id", "org_id", name="uq_multi_entity_roles_user_org"),
    )
    op.create_index("ix_multi_entity_roles_user_id", "multi_entity_roles", ["user_id"])
    op.create_index("ix_multi_entity_roles_org_id",  "multi_entity_roles", ["org_id"])

    # ── okr_objectives ─────────────────────────────────────────────────────────
    op.create_table(
        "okr_objectives",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", UUID(as_uuid=True),
                  sa.ForeignKey("okr_objectives.id", ondelete="SET NULL"), nullable=True),
        sa.Column("owner_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("level", sa.String(20), nullable=False, server_default="company"),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("period_label", sa.String(20), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("progress_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("created_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_okr_objectives_org_id",   "okr_objectives", ["org_id"])
    op.create_index("ix_okr_objectives_parent_id", "okr_objectives", ["parent_id"])

    # ── okr_key_results ────────────────────────────────────────────────────────
    op.create_table(
        "okr_key_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("objective_id", UUID(as_uuid=True),
                  sa.ForeignKey("okr_objectives.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("target_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("current_value", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(30), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="on_track"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_okr_key_results_objective_id", "okr_key_results", ["objective_id"])

    # ── ALTER budgets — department workflow fields ──────────────────────────────
    op.add_column("budgets", sa.Column("department", sa.String(100), nullable=True))
    op.add_column("budgets", sa.Column("submitted_by_user_id",
                                       UUID(as_uuid=True), nullable=True))
    op.add_column("budgets", sa.Column("submitted_at",
                                       sa.DateTime(timezone=True), nullable=True))
    op.add_column("budgets", sa.Column("review_notes", sa.Text(), nullable=True))
    op.add_column("budgets", sa.Column("locked_at",
                                       sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("budgets", "locked_at")
    op.drop_column("budgets", "review_notes")
    op.drop_column("budgets", "submitted_at")
    op.drop_column("budgets", "submitted_by_user_id")
    op.drop_column("budgets", "department")

    op.drop_index("ix_okr_key_results_objective_id", table_name="okr_key_results")
    op.drop_table("okr_key_results")

    op.drop_index("ix_okr_objectives_parent_id", table_name="okr_objectives")
    op.drop_index("ix_okr_objectives_org_id",   table_name="okr_objectives")
    op.drop_table("okr_objectives")

    op.drop_index("ix_multi_entity_roles_org_id",  table_name="multi_entity_roles")
    op.drop_index("ix_multi_entity_roles_user_id", table_name="multi_entity_roles")
    op.drop_table("multi_entity_roles")
