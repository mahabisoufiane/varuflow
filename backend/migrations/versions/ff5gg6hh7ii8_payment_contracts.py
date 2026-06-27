"""payment options + portal contracts/terms

Revision ID: ff5gg6hh7ii8
Revises: ee4ff5gg6hh7
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "ff5gg6hh7ii8"
down_revision = "ee4ff5gg6hh7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Payment plans / instalment options
    op.create_table(
        "payment_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("num_instalments", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payment_plans_org_invoice", "payment_plans", ["org_id", "invoice_id"])

    op.create_table(
        "payment_plan_instalments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("plan_id", UUID(as_uuid=True), sa.ForeignKey("payment_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("instalment_number", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
    )
    op.create_index("ix_payment_plan_instalments_plan", "payment_plan_instalments", ["plan_id"])

    # Early payment discounts
    op.create_table(
        "early_payment_discounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("discount_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("days_threshold", sa.Integer(), nullable=False),
        sa.Column("discounted_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_early_payment_discounts_org_inv", "early_payment_discounts", ["org_id", "invoice_id"])

    # Deposit requests
    op.create_table(
        "deposit_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("quote_id", UUID(as_uuid=True), sa.ForeignKey("quotes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_method", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_deposit_requests_org_cust", "deposit_requests", ["org_id", "customer_id"])

    # Portal terms acceptance
    op.create_table(
        "portal_terms_acceptances",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("terms_version", sa.String(50), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
    )
    op.create_index("ix_portal_terms_org_cust", "portal_terms_acceptances", ["org_id", "customer_id"])

    # NDA tracking
    op.create_table(
        "nda_agreements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signer_name", sa.String(200), nullable=True),
        sa.Column("signer_email", sa.String(254), nullable=True),
        sa.Column("signature_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_nda_agreements_org_cust", "nda_agreements", ["org_id", "customer_id"])

    # Add payment_method choices to invoices for alternative methods
    op.add_column("invoices", sa.Column("available_payment_methods", sa.String(200), nullable=True))
    op.add_column("invoices", sa.Column("early_payment_discount_pct", sa.Numeric(5, 2), nullable=True))
    op.add_column("invoices", sa.Column("early_payment_days", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("invoices", "early_payment_days")
    op.drop_column("invoices", "early_payment_discount_pct")
    op.drop_column("invoices", "available_payment_methods")
    op.drop_table("nda_agreements")
    op.drop_table("portal_terms_acceptances")
    op.drop_table("deposit_requests")
    op.drop_table("early_payment_discounts")
    op.drop_table("payment_plan_instalments")
    op.drop_table("payment_plans")
