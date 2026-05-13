"""bom enhancements: drop unique constraint, add version/is_default/yield_percent/scrap_rate/cost_override

Revision ID: cc3dd4ee5ff6
Revises: bb2cc3dd4ee5
Create Date: 2026-05-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "cc3dd4ee5ff6"
down_revision = "bb2cc3dd4ee5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the unique constraint that prevents multiple BOMs per product
    op.drop_constraint("uq_bom_headers_org_product", "bom_headers", type_="unique")

    # Add new columns
    op.add_column("bom_headers", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("bom_headers", sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("bom_headers", sa.Column("yield_percent", sa.Numeric(5, 2), nullable=False, server_default="100"))
    op.add_column("bom_headers", sa.Column("scrap_rate", sa.Numeric(5, 2), nullable=False, server_default="0"))
    op.add_column("bom_headers", sa.Column("cost_override", sa.Numeric(14, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("bom_headers", "cost_override")
    op.drop_column("bom_headers", "scrap_rate")
    op.drop_column("bom_headers", "yield_percent")
    op.drop_column("bom_headers", "is_default")
    op.drop_column("bom_headers", "version")

    op.create_unique_constraint(
        "uq_bom_headers_org_product", "bom_headers", ["org_id", "product_id"]
    )
