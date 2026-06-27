"""job_cards — field-service work order tables

Revision ID: uu1vv2ww3xx4
Revises: tt0uu1vv2ww3
Create Date: 2026-05-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "uu1vv2ww3xx4"
down_revision = "tt0uu1vv2ww3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_number", sa.String(50), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assigned_staff_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("site_address", sa.Text, nullable=True),
        sa.Column("scheduled_date", sa.Date, nullable=True),
        sa.Column("estimated_hours", sa.Numeric(6, 2), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("customer_signature_url", sa.String(1024), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_job_cards_org_id", "job_cards", ["org_id"])
    op.create_index("ix_job_cards_customer_id", "job_cards", ["customer_id"])
    op.create_index("ix_job_cards_status", "job_cards", ["status"])

    op.create_table(
        "job_card_parts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_card_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_cards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_job_card_parts_job_card_id", "job_card_parts", ["job_card_id"])

    op.create_table(
        "job_card_labour",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_card_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_cards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("staff_name", sa.String(255), nullable=True),
        sa.Column("hours", sa.Numeric(6, 2), nullable=False),
        sa.Column("hourly_rate", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_job_card_labour_job_card_id", "job_card_labour", ["job_card_id"])

    op.create_table(
        "job_card_photos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_card_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("job_cards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("caption", sa.String(200), nullable=True),
        sa.Column("photo_type", sa.String(10), nullable=False, server_default="before"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_job_card_photos_job_card_id", "job_card_photos", ["job_card_id"])


def downgrade() -> None:
    op.drop_table("job_card_photos")
    op.drop_table("job_card_labour")
    op.drop_table("job_card_parts")
    op.drop_table("job_cards")
