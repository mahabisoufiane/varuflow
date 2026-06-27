"""Add client_sync_id to invoices for offline sync idempotency.

Revision ID: pp7qq8rr9ss0
Revises: oo6pp7qq8rr9
Create Date: 2026-05-01

When a mobile client creates an invoice offline and later syncs, the server
may receive the same payload twice (retry, reconnection). client_sync_id is
a client-generated UUID4; the POST endpoint returns the existing invoice
rather than creating a duplicate if this ID is already on file.
"""
from alembic import op
import sqlalchemy as sa

revision = "pp7qq8rr9ss0"
down_revision = "oo6pp7qq8rr9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column("client_sync_id", sa.String(36), nullable=True),
    )
    # Unique per org to prevent double-sync; allows NULL for non-offline invoices
    op.create_index(
        "ix_invoices_client_sync_id",
        "invoices",
        ["org_id", "client_sync_id"],
        unique=True,
        postgresql_where=sa.text("client_sync_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_invoices_client_sync_id", table_name="invoices")
    op.drop_column("invoices", "client_sync_id")
