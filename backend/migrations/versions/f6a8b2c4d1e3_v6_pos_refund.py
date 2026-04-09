"""v6_pos_refund — add is_refunded / refunded_at to pos_sales

Revision ID: f6a8b2c4d1e3
Revises: e5f7a1b4c6d8
Create Date: 2026-04-09 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a8b2c4d1e3"
down_revision: Union[str, None] = "e5f7a1b4c6d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pos_sales", sa.Column("is_refunded", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("pos_sales", sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("ALTER TABLE pos_sales ADD COLUMN IF NOT EXISTS customer_id UUID")
    op.create_index("ix_pos_sales_customer_id", "pos_sales", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_pos_sales_customer_id", table_name="pos_sales")
    op.execute("ALTER TABLE pos_sales DROP COLUMN IF EXISTS customer_id")
    op.drop_column("pos_sales", "refunded_at")
    op.drop_column("pos_sales", "is_refunded")
