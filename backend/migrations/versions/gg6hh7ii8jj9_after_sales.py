"""after-sales: returns, warranty, satisfaction surveys, upsell suggestions

Revision ID: gg6hh7ii8jj9
Revises: ff5gg6hh7ii8
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "gg6hh7ii8jj9"
down_revision = "ff5gg6hh7ii8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Return / Refund requests ──────────────────────────────────────────────
    op.create_table(
        "return_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        # quantity requested for return (NULL = whole line)
        sa.Column("quantity", sa.Numeric(10, 3), nullable=True),
        sa.Column("reason", sa.String(50), nullable=False, server_default="other"),
        # defective / wrong_item / not_as_described / changed_mind / other
        sa.Column("description", sa.Text(), nullable=True),
        # pending / approved / rejected / refunded / exchanged
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("refund_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_return_requests_org_customer", "return_requests", ["org_id", "customer_id"])
    op.create_index("ix_return_requests_org_status", "return_requests", ["org_id", "status"])

    # ── Warranty records ──────────────────────────────────────────────────────
    op.create_table(
        "warranty_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("serial_number", sa.String(100), nullable=True),
        sa.Column("product_name_snapshot", sa.String(500), nullable=True),
        sa.Column("warranty_months", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("starts_at", sa.Date(), nullable=False),
        sa.Column("expires_at", sa.Date(), nullable=False),
        # active / expired / voided / claimed
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_warranty_records_org_customer", "warranty_records", ["org_id", "customer_id"])
    op.create_index("ix_warranty_records_org_product", "warranty_records", ["org_id", "product_id"])
    op.create_index("ix_warranty_records_expires", "warranty_records", ["expires_at"])

    # ── Satisfaction surveys ──────────────────────────────────────────────────
    op.create_table(
        "satisfaction_surveys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        # invoice / project / appointment
        sa.Column("reference_type", sa.String(30), nullable=False),
        sa.Column("reference_id", UUID(as_uuid=True), nullable=False),
        # score 1-5
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        # signed token for magic-link submission (no portal login required)
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_satisfaction_surveys_org_customer", "satisfaction_surveys", ["org_id", "customer_id"])
    op.create_index("ix_satisfaction_surveys_org_ref", "satisfaction_surveys", ["org_id", "reference_type", "reference_id"])

    # ── Upsell / cross-sell suggestions ──────────────────────────────────────
    op.create_table(
        "upsell_suggestions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        # post_invoice / post_project / post_appointment
        sa.Column("trigger_type", sa.String(30), nullable=False),
        sa.Column("trigger_id", UUID(as_uuid=True), nullable=False),
        # comma-separated product UUIDs or names
        sa.Column("product_ids", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("shown_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_upsell_suggestions_org_customer", "upsell_suggestions", ["org_id", "customer_id"])
    op.create_index("ix_upsell_suggestions_trigger", "upsell_suggestions", ["org_id", "trigger_type", "trigger_id"])


def downgrade() -> None:
    op.drop_table("upsell_suggestions")
    op.drop_table("satisfaction_surveys")
    op.drop_table("warranty_records")
    op.drop_table("return_requests")
