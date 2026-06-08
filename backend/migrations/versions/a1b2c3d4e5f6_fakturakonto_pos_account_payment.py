"""Add ACCOUNT value to pos_payment_method enum (Fakturakonto)

Revision ID: a1b2c3d4e5f6
Revises: z3t4u5v6w7x8
Create Date: 2026-06-08

"""
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "z3t4u5v6w7x8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL requires ALTER TYPE to add a new enum value.
    # IF NOT EXISTS prevents errors on re-runs (idempotent).
    op.execute("ALTER TYPE pos_payment_method ADD VALUE IF NOT EXISTS 'ACCOUNT'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without recreating
    # the type. Downgrade is intentionally a no-op — the value is harmless
    # when unused, and removing it would require a full type recreation plus
    # column rewrite with a table lock on pos_sales.
    pass
