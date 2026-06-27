"""fixed_assets v2 — supplier, PO link, expense link

Revision ID: ff6gg7hh8ii9
Revises: ee5ff6gg7hh8
Create Date: 2026-04-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "ff6gg7hh8ii9"
down_revision = "ee5ff6gg7hh8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fixed_assets", sa.Column("supplier", sa.String(200), nullable=True))
    op.add_column(
        "fixed_assets",
        sa.Column(
            "purchase_order_id",
            UUID(as_uuid=True),
            sa.ForeignKey("purchase_orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "fixed_assets",
        sa.Column(
            "expense_id",
            UUID(as_uuid=True),
            sa.ForeignKey("expenses.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_fixed_assets_po_id", "fixed_assets", ["purchase_order_id"])
    op.create_index("ix_fixed_assets_expense_id", "fixed_assets", ["expense_id"])


def downgrade() -> None:
    op.drop_index("ix_fixed_assets_expense_id", table_name="fixed_assets")
    op.drop_index("ix_fixed_assets_po_id", table_name="fixed_assets")
    op.drop_column("fixed_assets", "expense_id")
    op.drop_column("fixed_assets", "purchase_order_id")
    op.drop_column("fixed_assets", "supplier")
