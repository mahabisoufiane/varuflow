"""growth1: partner_programs, pricing_experiments, market_expansion_checklists, churn fields on customers

Revision ID: e8y9z0a1b2c3
Revises: d7x8y9z0a1b2
Create Date: 2026-04-30 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

revision = "e8y9z0a1b2c3"
down_revision = "d7x8y9z0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # partner_programs — commission tiers for B2B affiliates
    op.create_table(
        "partner_programs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("commission_type", sa.String(20), nullable=False, server_default="percentage"),  # percentage | fixed
        sa.Column("commission_rate", sa.Numeric(10, 4), nullable=False, server_default="0.05"),
        sa.Column("min_deal_value", sa.Numeric(18, 2), nullable=True),
        sa.Column("payout_threshold", sa.Numeric(18, 2), nullable=False, server_default="500"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_partner_programs_org_id", "partner_programs", ["org_id"])

    # partners — individual B2B partner companies
    op.create_table(
        "partners",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("program_id", UUID(as_uuid=True), sa.ForeignKey("partner_programs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("company_name", sa.String(200), nullable=False),
        sa.Column("contact_name", sa.String(200), nullable=True),
        sa.Column("contact_email", sa.String(254), nullable=False),
        sa.Column("referral_code", sa.String(32), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),  # pending|active|suspended|terminated
        sa.Column("total_referred_revenue", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_commission_earned", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_commission_paid", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_partners_org_id", "partners", ["org_id"])
    op.create_index("ix_partners_program_id", "partners", ["program_id"])

    # partner_deals — revenue credited to a partner
    op.create_table(
        "partner_deals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("partner_id", UUID(as_uuid=True), sa.ForeignKey("partners.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("invoice_id", UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("deal_name", sa.String(200), nullable=True),
        sa.Column("stage", sa.String(30), nullable=False, server_default="registered"),  # registered|approved|paid
        sa.Column("deal_value", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("commission_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_partner_deals_org_id", "partner_deals", ["org_id"])
    op.create_index("ix_partner_deals_partner_id", "partner_deals", ["partner_id"])

    # pricing_experiments — A/B test invoice price rules
    op.create_table(
        "pricing_experiments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),  # draft|active|paused|completed
        sa.Column("control_label", sa.String(100), nullable=False, server_default="Control"),
        sa.Column("variant_label", sa.String(100), nullable=False, server_default="Variant"),
        sa.Column("control_price_pct_change", sa.Numeric(8, 4), nullable=False, server_default="0"),  # 0 = no change
        sa.Column("variant_price_pct_change", sa.Numeric(8, 4), nullable=False, server_default="0.1"),  # 10% increase
        sa.Column("assigned_control_ids", JSONB, nullable=False, server_default="[]"),   # customer UUIDs
        sa.Column("assigned_variant_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_pricing_experiments_org_id", "pricing_experiments", ["org_id"])

    # market_expansion_checklists — per-country expansion readiness
    op.create_table(
        "market_expansion_checklists",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),   # ISO 3166-1 alpha-2
        sa.Column("country_name", sa.String(100), nullable=False),
        sa.Column("items", JSONB, nullable=False, server_default="[]"),  # [{id, category, title, done, notes}]
        sa.Column("completion_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("target_launch_date", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("org_id", "country_code", name="uq_market_checklist_org_country"),
    )
    op.create_index("ix_market_expansion_checklists_org_id", "market_expansion_checklists", ["org_id"])

    # Add churn tracking columns to customers
    op.add_column("customers", sa.Column("churned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("customers", sa.Column("churn_reason", sa.String(100), nullable=True))
    op.add_column("customers", sa.Column("churn_score", sa.Numeric(5, 2), nullable=True))  # 0-100 risk score


def downgrade() -> None:
    op.drop_column("customers", "churn_score")
    op.drop_column("customers", "churn_reason")
    op.drop_column("customers", "churned_at")
    op.drop_index("ix_market_expansion_checklists_org_id", "market_expansion_checklists")
    op.drop_table("market_expansion_checklists")
    op.drop_index("ix_pricing_experiments_org_id", "pricing_experiments")
    op.drop_table("pricing_experiments")
    op.drop_index("ix_partner_deals_partner_id", "partner_deals")
    op.drop_index("ix_partner_deals_org_id", "partner_deals")
    op.drop_table("partner_deals")
    op.drop_index("ix_partners_program_id", "partners")
    op.drop_index("ix_partners_org_id", "partners")
    op.drop_table("partners")
    op.drop_index("ix_partner_programs_org_id", "partner_programs")
    op.drop_table("partner_programs")
