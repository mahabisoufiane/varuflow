"""vA5 — Bank Feed / CSV Import

Revision ID: e4f5a6b7c8d9
Revises:     d3e4f5a6b7c8
Create Date: 2026-04-30

Adds:
  bank_accounts     — org bank account record
  bank_transactions — imported CSV transactions with dedup UniqueConstraint
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bank_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("iban", sa.String(34), nullable=True),
        sa.Column("currency", sa.String(3), server_default="SEK", nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_bank_accounts_org_id", "bank_accounts", ["org_id"])

    op.create_table(
        "bank_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), server_default="UNMATCHED", nullable=False),
        sa.Column("matched_type", sa.String(30), nullable=True),
        sa.Column("matched_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("bank_account_id", "transaction_date", "amount", "description", name="uq_bank_tx_dedup"),
    )
    op.create_index("ix_bank_transactions_account_id", "bank_transactions", ["bank_account_id"])
    op.create_index("ix_bank_transactions_org_id", "bank_transactions", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_bank_transactions_org_id", table_name="bank_transactions")
    op.drop_index("ix_bank_transactions_account_id", table_name="bank_transactions")
    op.drop_table("bank_transactions")
    op.drop_index("ix_bank_accounts_org_id", table_name="bank_accounts")
    op.drop_table("bank_accounts")
