"""vA4 — Budget vs Actual

Revision ID: d3e4f5a6b7c8
Revises:     c2d3e4f5a6b7
Create Date: 2026-04-30

Adds:
  budgets      — fiscal-year budget (DRAFT → APPROVED)
  budget_lines — monthly amount per account code
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "budgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="DRAFT", nullable=False),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_budgets_org_id", "budgets", ["org_id"])

    op.create_table(
        "budget_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("budget_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_code", sa.String(10), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.UniqueConstraint("budget_id", "account_code", "month", name="uq_budget_line"),
    )
    op.create_index("ix_budget_lines_budget_id", "budget_lines", ["budget_id"])


def downgrade() -> None:
    op.drop_index("ix_budget_lines_budget_id", table_name="budget_lines")
    op.drop_table("budget_lines")
    op.drop_index("ix_budgets_org_id", table_name="budgets")
    op.drop_table("budgets")
