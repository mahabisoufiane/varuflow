"""bom_cost_per_unit - add cost_per_unit to bom_lines

Revision ID: aa8b9c0d1e2f
Revises: z3t4u5v6w7x8
Create Date: 2026-06-08
"""

from alembic import op
import sqlalchemy as sa

revision = "aa8b9c0d1e2f"
down_revision = "z3t4u5v6w7x8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bom_lines",
        sa.Column("cost_per_unit", sa.Numeric(14, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bom_lines", "cost_per_unit")
