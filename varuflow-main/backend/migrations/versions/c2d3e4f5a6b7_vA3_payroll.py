"""vA3 — Payroll processing

Revision ID: c2d3e4f5a6b7
Revises:     b1c2d3e4f5a6
Create Date: 2026-04-30

Adds:
  payroll_runs    — payroll batch per period (DRAFT → APPROVED → PAID)
  payroll_entries — per-employee salary breakdown within a run
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payroll_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), server_default="DRAFT", nullable=False),
        sa.Column("total_gross", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("total_employer_cost", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payroll_runs_org_id", "payroll_runs", ["org_id"])

    op.create_table(
        "payroll_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("payroll_run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("employee_name", sa.String(200), nullable=False),
        sa.Column("personal_number", sa.String(256), nullable=True),  # encrypted at rest
        sa.Column("gross_salary", sa.Numeric(14, 2), nullable=False),
        sa.Column("income_tax", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("social_contribution", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("net_salary", sa.Numeric(14, 2), nullable=False),
        sa.Column("employer_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payroll_entries_run_id", "payroll_entries", ["payroll_run_id"])


def downgrade() -> None:
    op.drop_index("ix_payroll_entries_run_id", table_name="payroll_entries")
    op.drop_table("payroll_entries")
    op.drop_index("ix_payroll_runs_org_id", table_name="payroll_runs")
    op.drop_table("payroll_runs")
