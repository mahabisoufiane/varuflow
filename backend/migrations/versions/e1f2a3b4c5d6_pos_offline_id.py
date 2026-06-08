"""Add offline_id to pos_sales for idempotent offline sync.

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3a4b5c6
Create Date: 2026-06-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "e1f2a3b4c5d6"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pos_sales", sa.Column("offline_id", pg.UUID(as_uuid=True), nullable=True))
    # Partial unique index ensures uniqueness only when offline_id is set.
    # Multiple NULLs are allowed (PostgreSQL treats NULL != NULL in UNIQUE
    # constraints, so the UniqueConstraint on the model also works, but
    # an explicit partial index avoids the index scanning NULL rows).
    op.create_index(
        "ix_pos_sales_org_offline_id",
        "pos_sales",
        ["org_id", "offline_id"],
        unique=True,
        postgresql_where=sa.text("offline_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_pos_sales_org_offline_id", table_name="pos_sales")
    op.drop_column("pos_sales", "offline_id")
