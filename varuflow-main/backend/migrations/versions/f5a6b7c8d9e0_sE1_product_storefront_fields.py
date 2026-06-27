"""sE1 — Product storefront fields (slug + image_url)

Revision ID: f5a6b7c8d9e0
Revises:     e4f5a6b7c8d9
Create Date: 2026-04-30

Adds slug (unique) and image_url to the products table.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f5a6b7c8d9e0"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    cols = {
        r[0]
        for r in conn.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='products'"
            )
        )
    }
    if "slug" not in cols:
        op.add_column("products", sa.Column("slug", sa.String(120), nullable=True))
    if "image_url" not in cols:
        op.add_column("products", sa.Column("image_url", sa.Text(), nullable=True))
    idxs = {
        r[0]
        for r in conn.execute(
            sa.text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename='products' AND indexname='ix_products_slug'"
            )
        )
    }
    if "ix_products_slug" not in idxs:
        op.create_index("ix_products_slug", "products", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_products_slug", table_name="products")
    op.drop_column("products", "image_url")
    op.drop_column("products", "slug")
