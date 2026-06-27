"""phase4 - soft delete columns on four business-critical tables

Revision ID: aaaa11110001
Revises: z3t4u5v6w7x8
Create Date: 2026-06-14
"""

from alembic import op
import sqlalchemy as sa

revision = "aaaa11110001"
down_revision = "z3t4u5v6w7x8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NULL = active row; non-NULL = soft-deleted at that timestamp.
    # Router-level filtering (exclude deleted) is opt-in per endpoint.
    op.add_column("organizations", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("customers", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invoices", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("products", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "deleted_at")
    op.drop_column("invoices", "deleted_at")
    op.drop_column("customers", "deleted_at")
    op.drop_column("organizations", "deleted_at")
