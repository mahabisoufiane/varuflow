"""mena1 - zatca invoices

Revision ID: w0q1r2s3t4u5
Revises: v9p1q2r3s4t5
Create Date: 2026-04-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "w0q1r2s3t4u5"
down_revision = "v9p1q2r3s4t5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "zatca_invoices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("invoice_id", UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("invoice_hash", sa.String(64), nullable=False),
        sa.Column("qr_tlv_b64", sa.Text(), nullable=False),
        sa.Column("xml_content", sa.Text(), nullable=False),
        sa.Column("clearance_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("clearance_response", JSONB(), nullable=True),
        sa.Column("zatca_uuid", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("zatca_invoices")
