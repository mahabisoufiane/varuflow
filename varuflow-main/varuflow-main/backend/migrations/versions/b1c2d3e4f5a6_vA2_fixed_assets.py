"""vA2 — Fixed asset register

Revision ID: b1c2d3e4f5a6
Revises:     a0b1c2d3e4f5
Create Date: 2026-04-30

Adds:
  fixed_assets         — capital asset definitions with depreciation schedule config
  asset_depreciations  — per-period depreciation entries, linked to journal_entries
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b1c2d3e4f5a6"
down_revision = "a0b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fixed_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(40), server_default="EQUIPMENT", nullable=False),
        sa.Column("acquisition_date", sa.Date(), nullable=False),
        sa.Column("acquisition_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("salvage_value", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("useful_life_years", sa.Integer(), nullable=False),
        sa.Column("depreciation_method", sa.String(30), server_default="STRAIGHT_LINE", nullable=False),
        sa.Column("current_book_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("account_code", sa.String(10), server_default="1710", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_disposed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("disposed_at", sa.Date(), nullable=True),
        sa.Column("disposal_proceeds", sa.Numeric(14, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_fixed_assets_org_id", "fixed_assets", ["org_id"])

    op.create_table(
        "asset_depreciations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("fixed_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_asset_dep_asset_id", "asset_depreciations", ["asset_id"])
    op.create_unique_constraint("uq_asset_depreciation_period", "asset_depreciations", ["asset_id", "period"])


def downgrade() -> None:
    op.drop_constraint("uq_asset_depreciation_period", "asset_depreciations")
    op.drop_index("ix_asset_dep_asset_id", table_name="asset_depreciations")
    op.drop_table("asset_depreciations")
    op.drop_index("ix_fixed_assets_org_id", table_name="fixed_assets")
    op.drop_table("fixed_assets")
