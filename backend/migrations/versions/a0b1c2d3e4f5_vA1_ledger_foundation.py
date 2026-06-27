"""vA1 — Double-entry ledger foundation

Revision ID: a0b1c2d3e4f5
Revises:     d0e2f4a9b2c5, b9c1d3e5f7a8
Create Date: 2026-04-30

Merges the two existing branch heads and adds three tables for the
double-entry bookkeeping engine:

  chart_of_accounts  — BAS 2024 account definitions per org (seeded at
                        first use by the router).
  journal_entries    — one balanced verification per bookkeeping event.
  journal_lines      — individual debit / credit legs, linked to an entry.

The ``(org_id, source_type, source_id)`` unique constraint on
journal_entries makes the backfill endpoint idempotent: posting the
same invoice twice is a silent no-op.

Account codes on journal_lines are denormalised (snapshot) so that
renaming a chart-of-accounts entry does not corrupt history.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a0b1c2d3e4f5"
down_revision = ("d0e2f4a9b2c5", "b9c1d3e5f7a8")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── chart_of_accounts ──────────────────────────────────────────
    op.create_table(
        "chart_of_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column(
            "account_type",
            sa.Enum(
                "ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE",
                name="account_type_enum",
            ),
            nullable=False,
        ),
        sa.Column("account_subtype", sa.String(40), nullable=True),
        sa.Column("is_system", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_coa_org_id", "chart_of_accounts", ["org_id"])
    op.create_unique_constraint("uq_coa_org_code", "chart_of_accounts", ["org_id", "code"])

    # ── journal_entries ────────────────────────────────────────────
    op.create_table(
        "journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reference", sa.String(120), nullable=True),
        sa.Column("is_posted", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_journal_entry_org_date", "journal_entries", ["org_id", "entry_date"])
    op.create_unique_constraint(
        "uq_journal_entry_source",
        "journal_entries",
        ["org_id", "source_type", "source_id"],
    )

    # ── journal_lines ──────────────────────────────────────────────
    op.create_table(
        "journal_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "journal_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_code", sa.String(10), nullable=False),
        sa.Column("debit", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("credit", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("memo", sa.String(255), nullable=True),
        sa.Column("currency", sa.String(3), server_default="SEK", nullable=False),
    )
    op.create_index("ix_journal_lines_entry_id", "journal_lines", ["journal_entry_id"])
    op.create_index("ix_journal_lines_account_code", "journal_lines", ["account_code"])


def downgrade() -> None:
    op.drop_table("journal_lines")
    op.drop_index("ix_journal_entry_org_date", table_name="journal_entries")
    op.drop_constraint("uq_journal_entry_source", "journal_entries")
    op.drop_table("journal_entries")
    op.drop_index("ix_coa_org_id", table_name="chart_of_accounts")
    op.drop_constraint("uq_coa_org_code", "chart_of_accounts")
    op.drop_table("chart_of_accounts")
    op.execute("DROP TYPE IF EXISTS account_type_enum")
