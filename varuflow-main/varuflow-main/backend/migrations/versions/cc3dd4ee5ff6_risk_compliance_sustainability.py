"""Risk, Compliance, and Sustainability tables.

Revision ID: cc3dd4ee5ff6
Revises:     bb1cc2dd3ee4
Create Date: 2026-05-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "cc3dd4ee5ff6"
down_revision = "bb1cc2dd3ee4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── risk_items ──────────────────────────────────────────────────────────────
    op.create_table(
        "risk_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("category", sa.String(50), nullable=False, server_default="other"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("likelihood", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("impact", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("risk_score", sa.Numeric(4, 1), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="identified"),
        sa.Column("mitigation_plan", sa.Text(), nullable=True),
        sa.Column("owner_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("last_reviewed", sa.Date(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_risk_items_org_id", "risk_items", ["org_id"])

    # ── insurance_policies ──────────────────────────────────────────────────────
    op.create_table(
        "insurance_policies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("policy_name", sa.String(200), nullable=False),
        sa.Column("insurer", sa.String(200), nullable=True),
        sa.Column("policy_number", sa.String(100), nullable=True),
        sa.Column("type", sa.String(50), nullable=False, server_default="other"),
        sa.Column("coverage_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("premium_annual", sa.Numeric(18, 2), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("renewal_due", sa.Date(), nullable=True),
        sa.Column("renewal_reminder_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_insurance_policies_org_id", "insurance_policies", ["org_id"])

    # ── insurance_claims ────────────────────────────────────────────────────────
    op.create_table(
        "insurance_claims",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("policy_id", UUID(as_uuid=True),
                  sa.ForeignKey("insurance_policies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claim_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount_claimed", sa.Numeric(18, 2), nullable=True),
        sa.Column("amount_settled", sa.Numeric(18, 2), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("settled_at", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_insurance_claims_policy_id", "insurance_claims", ["policy_id"])
    op.create_index("ix_insurance_claims_org_id",   "insurance_claims", ["org_id"])

    # ── regulatory_events ───────────────────────────────────────────────────────
    op.create_table(
        "regulatory_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False, server_default="other"),
        sa.Column("country", sa.String(3), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("recurrence", sa.String(20), nullable=False, server_default="once"),
        sa.Column("status", sa.String(20), nullable=False, server_default="upcoming"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("alert_days", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_regulatory_events_org_id",   "regulatory_events", ["org_id"])
    op.create_index("ix_regulatory_events_due_date", "regulatory_events", ["due_date"])

    # ── whistleblower_reports ───────────────────────────────────────────────────
    op.create_table(
        "whistleblower_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("category", sa.String(50), nullable=False, server_default="other"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_anonymous", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("reporter_contact", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("assigned_to_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_whistleblower_reports_org_id", "whistleblower_reports", ["org_id"])
    op.create_index("ix_whistleblower_reports_token",  "whistleblower_reports", ["token"], unique=True)

    # ── conflict_declarations ───────────────────────────────────────────────────
    op.create_table(
        "conflict_declarations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("declaration_type", sa.String(50), nullable=False),
        sa.Column("counterparty_name", sa.String(300), nullable=False),
        sa.Column("counterparty_type", sa.String(50), nullable=True),
        sa.Column("relationship_description", sa.Text(), nullable=True),
        sa.Column("declared_value", sa.Numeric(18, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("is_reviewed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("reviewed_by", UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_conflict_declarations_org_id",  "conflict_declarations", ["org_id"])
    op.create_index("ix_conflict_declarations_user_id", "conflict_declarations", ["user_id"])

    # ── carbon_entries ──────────────────────────────────────────────────────────
    op.create_table(
        "carbon_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.Integer(), nullable=False),   # 1, 2, or 3
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("emission_factor", sa.Numeric(14, 6), nullable=True),
        sa.Column("co2_kg", sa.Numeric(16, 4), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("data_source", sa.String(100), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_carbon_entries_org_id",     "carbon_entries", ["org_id"])
    op.create_index("ix_carbon_entries_period_start", "carbon_entries", ["period_start"])

    # ── esg_reports ─────────────────────────────────────────────────────────────
    op.create_table(
        "esg_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("report_year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        # Environmental
        sa.Column("total_co2_tonnes", sa.Numeric(14, 4), nullable=True),
        sa.Column("co2_per_revenue", sa.Numeric(14, 6), nullable=True),
        sa.Column("renewable_energy_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("waste_recycled_pct", sa.Numeric(5, 2), nullable=True),
        # Social
        sa.Column("employee_count", sa.Integer(), nullable=True),
        sa.Column("female_leadership_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("training_hours_per_employee", sa.Numeric(8, 2), nullable=True),
        sa.Column("employee_satisfaction_score", sa.Numeric(4, 2), nullable=True),
        sa.Column("injury_rate", sa.Numeric(8, 4), nullable=True),
        # Governance
        sa.Column("audit_complete", sa.Boolean(), nullable=True),
        sa.Column("whistleblower_mechanism", sa.Boolean(), nullable=True),
        sa.Column("anti_corruption_training_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("board_diversity_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_esg_reports_org_id", "esg_reports", ["org_id"])

    # ── supplier_sustainability_ratings ─────────────────────────────────────────
    op.create_table(
        "supplier_sustainability_ratings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_id", UUID(as_uuid=True),
                  sa.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("environmental_score", sa.Integer(), nullable=True),
        sa.Column("social_score", sa.Integer(), nullable=True),
        sa.Column("governance_score", sa.Integer(), nullable=True),
        sa.Column("overall_score", sa.Integer(), nullable=True),
        sa.Column("certifications", JSONB(), nullable=True),
        sa.Column("ethical_sourcing_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_audit_date", sa.Date(), nullable=True),
        sa.Column("next_audit_date", sa.Date(), nullable=True),
        sa.Column("audit_notes", sa.Text(), nullable=True),
        sa.Column("risk_level", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", "supplier_id", name="uq_supplier_sustainability_org_supplier"),
    )
    op.create_index("ix_supplier_sustainability_org_id",     "supplier_sustainability_ratings", ["org_id"])
    op.create_index("ix_supplier_sustainability_supplier_id", "supplier_sustainability_ratings", ["supplier_id"])


def downgrade() -> None:
    op.drop_table("supplier_sustainability_ratings")
    op.drop_table("esg_reports")
    op.drop_table("carbon_entries")
    op.drop_table("conflict_declarations")
    op.drop_table("whistleblower_reports")
    op.drop_table("regulatory_events")
    op.drop_table("insurance_claims")
    op.drop_table("insurance_policies")
    op.drop_table("risk_items")
