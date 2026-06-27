"""Add invoice_type, deposit_amount, parent_invoice_id to invoices

Revision ID: cc3dd4ee5ff6
Revises: bb2cc3dd4ee5
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "cc3dd4ee5ff6"
down_revision = "bb2cc3dd4ee5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column(
        "invoice_type", sa.String(20), nullable=False, server_default="standard"
    ))
    op.add_column("invoices", sa.Column(
        "deposit_amount", sa.Numeric(14, 2), nullable=True
    ))
    op.add_column("invoices", sa.Column(
        "parent_invoice_id",
        UUID(as_uuid=True),
        sa.ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
    ))
    op.create_index("ix_invoices_parent_invoice_id", "invoices", ["parent_invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_invoices_parent_invoice_id", "invoices")
    op.drop_column("invoices", "parent_invoice_id")
    op.drop_column("invoices", "deposit_amount")
    op.drop_column("invoices", "invoice_type")
