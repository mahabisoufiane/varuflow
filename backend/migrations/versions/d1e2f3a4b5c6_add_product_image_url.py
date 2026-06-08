"""Add image_url column to products table.

Revision ID: d1e2f3a4b5c6
Revises: c5e7f1a3d8b9
Create Date: 2026-06-07

"""
from alembic import op
import sqlalchemy as sa

revision = "d1e2f3a4b5c6"
down_revision = "c5e7f1a3d8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("image_url", sa.String(2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("products", "image_url")
