"""v11: missing FK indexes on invoice/payment/portal/recurring tables

Revision ID: c5e7f1a3d8b9
Revises: b4d6f0a2c8e1
Create Date: 2026-04-21

CLAUDE.md Rule 5 requires every FK column to have a DB-level index.
This migration backfills indexes that were missed in earlier versions.

`if_not_exists=True` keeps the migration idempotent in case a DBA added
one of these indexes manually.
"""
from alembic import op

revision = "c5e7f1a3d8b9"
down_revision = "b4d6f0a2c8e1"
branch_labels = None
depends_on = None


_INDEXES = [
    ("ix_invoices_customer_id",                    "invoices",                 ["customer_id"]),
    ("ix_invoice_line_items_invoice_id",           "invoice_line_items",       ["invoice_id"]),
    ("ix_invoice_line_items_product_id",           "invoice_line_items",       ["product_id"]),
    ("ix_payments_invoice_id",                     "payments",                 ["invoice_id"]),
    ("ix_customer_portal_tokens_org_id",           "customer_portal_tokens",   ["org_id"]),
    ("ix_recurring_invoices_customer_id",          "recurring_invoices",       ["customer_id"]),
]


def upgrade() -> None:
    # Use raw SQL with IF NOT EXISTS for idempotency in case a DBA added
    # one of these indexes manually between releases.
    for name, table, cols in _INDEXES:
        cols_sql = ", ".join(cols)
        op.execute(f'CREATE INDEX IF NOT EXISTS {name} ON {table} ({cols_sql})')


def downgrade() -> None:
    for name, _, _ in reversed(_INDEXES):
        op.execute(f'DROP INDEX IF EXISTS {name}')
