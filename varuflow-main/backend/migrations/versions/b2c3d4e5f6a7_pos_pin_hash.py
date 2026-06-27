"""Add pos_pin_hash column to organization_members for POS tablet PIN auth

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-08

"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='organization_members' AND column_name='pos_pin_hash'"
        )
    ).fetchone()
    if not row:
        op.add_column(
            "organization_members",
            sa.Column("pos_pin_hash", sa.String(100), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("organization_members", "pos_pin_hash")
