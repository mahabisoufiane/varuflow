"""v102 – accounting_firm_partners + accounting_partner_referrals tables

Revision ID: a1b2p3a4r5t6
Revises: z3t4u5v6w7x8
Create Date: 2026-05-02
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a1b2p3a4r5t6"
down_revision = "z3t4u5v6w7x8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounting_firm_partners",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("firm_name", sa.String(200), nullable=False),
        sa.Column("contact_name", sa.String(200), nullable=False),
        sa.Column("contact_email", sa.String(1000), nullable=False),
        sa.Column("contact_phone", sa.String(1000), nullable=True),
        sa.Column("country", sa.String(2), nullable=False, server_default="SE"),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("referral_code", sa.String(30), nullable=False),
        sa.Column("commission_rate_pct", sa.Numeric(5, 2), nullable=False, server_default="25"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("bank_account", sa.String(2000), nullable=True),
        sa.Column("vat_number", sa.String(50), nullable=True),
        sa.Column("business_registration_number", sa.String(50), nullable=True),
        sa.Column("client_count_estimate", sa.Integer, nullable=True),
        sa.Column("application_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("referral_code", name="uq_afp_referral_code"),
    )
    op.create_index("ix_afp_status", "accounting_firm_partners", ["status"])
    op.create_index("ix_afp_country", "accounting_firm_partners", ["country"])

    op.create_table(
        "accounting_partner_referrals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_firm_partners.id", ondelete="CASCADE"), nullable=False),
        sa.Column("referred_org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="clicked"),
        sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signed_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("subscription_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("commission_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("months_remaining", sa.Integer, nullable=False, server_default="12"),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_apr_partner_id", "accounting_partner_referrals", ["partner_id"])
    op.create_index("ix_apr_referred_org_id", "accounting_partner_referrals", ["referred_org_id"])
    op.create_index("ix_apr_status", "accounting_partner_referrals", ["status"])


def downgrade() -> None:
    op.drop_index("ix_apr_status", "accounting_partner_referrals")
    op.drop_index("ix_apr_referred_org_id", "accounting_partner_referrals")
    op.drop_index("ix_apr_partner_id", "accounting_partner_referrals")
    op.drop_table("accounting_partner_referrals")
    op.drop_index("ix_afp_country", "accounting_firm_partners")
    op.drop_index("ix_afp_status", "accounting_firm_partners")
    op.drop_table("accounting_firm_partners")
