"""mena2 - gcc payment sessions

Revision ID: x1r2s3t4u5v6
Revises: w0q1r2s3t4u5
Create Date: 2026-04-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "x1r2s3t4u5v6"
down_revision = "w0q1r2s3t4u5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gcc_payment_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("invoice_id", UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_session_id", sa.String(200), nullable=True, index=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="initiated"),
        sa.Column("webhook_payload", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("gcc_payment_sessions")
