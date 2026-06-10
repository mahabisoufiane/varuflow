"""Add ACCOUNT value to pos_payment_method enum (Fakturakonto)

Revision ID: c0d1e2f3a4b5
Revises: 6005c017b2f6
Create Date: 2026-06-08

"""
from alembic import op

revision = "c0d1e2f3a4b5"
down_revision = "6005c017b2f6"
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
