"""me1 - multi-entity and franchise

Extends organizations with parent/subsidiary hierarchy and adds
intercompany, franchise agreement, and royalty billing tables.

Revision ID: a4u5v6w7x8y9
Revises: z3t4u5v6w7x8
Create Date: 2026-04-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "a4u5v6w7x8y9"
down_revision = "z3t4u5v6w7x8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extend organizations with hierarchy columns ────────────────────────────
    op.add_column("organizations", sa.Column(
        "parent_org_id", UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True, index=True,
    ))
    op.add_column("organizations", sa.Column(
        "entity_type", sa.String(20), nullable=False, server_default="standalone"
    ))  # standalone | subsidiary | franchisor | franchisee
    op.add_column("organizations", sa.Column(
        "legal_name", sa.String(200), nullable=True
    ))
    op.add_column("organizations", sa.Column(
        "reporting_currency", sa.String(3), nullable=True
    ))

    # ── Intercompany transfers ─────────────────────────────────────────────────
    op.create_table(
        "intercompany_transfers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("from_org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("to_org_id",   UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("transfer_type", sa.String(20), nullable=False),  # stock | cash | service
        sa.Column("product_id",  UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("quantity",    sa.Numeric(14, 4), nullable=True),
        sa.Column("transfer_price", sa.Numeric(14, 2), nullable=False),  # arm's-length price per unit / total
        sa.Column("currency",    sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),  # draft|posted|eliminated
        sa.Column("elimination_entry_id", UUID(as_uuid=True), nullable=True),
        sa.Column("reference",   sa.String(100), nullable=True),
        sa.Column("transfer_date", sa.Date(), nullable=False),
        sa.Column("created_at",  sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",  sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Elimination entries (intercompany profit/balance eliminations) ─────────
    op.create_table(
        "elimination_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("parent_org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("period",      sa.String(7), nullable=False),   # YYYY-MM
        sa.Column("entry_type",  sa.String(30), nullable=False),  # intercompany_revenue | intercompany_cogs | intercompany_receivable | intercompany_payable
        sa.Column("from_org_id", UUID(as_uuid=True), nullable=True),
        sa.Column("to_org_id",   UUID(as_uuid=True), nullable=True),
        sa.Column("amount",      sa.Numeric(16, 2), nullable=False),
        sa.Column("currency",    sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at",  sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Franchise agreements ───────────────────────────────────────────────────
    op.create_table(
        "franchise_agreements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("franchisor_org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("franchisee_org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True),
        # franchisee_org_id may be null during onboarding (org not yet created)
        sa.Column("franchisee_name",  sa.String(200), nullable=False),
        sa.Column("franchisee_email", sa.String(200), nullable=False),
        sa.Column("franchisee_country", sa.String(3), nullable=True),
        sa.Column("royalty_rate",     sa.Numeric(5, 4), nullable=False, server_default="0.05"),  # e.g. 0.05 = 5%
        sa.Column("royalty_basis",    sa.String(20), nullable=False, server_default="gross_revenue"),  # gross_revenue | net_revenue | fixed
        sa.Column("fixed_royalty_amount", sa.Numeric(14, 2), nullable=True),  # if royalty_basis = fixed
        sa.Column("currency",         sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("billing_cycle",    sa.String(10), nullable=False, server_default="monthly"),  # monthly|quarterly
        sa.Column("status",           sa.String(20), nullable=False, server_default="pending"),  # pending|active|terminated
        sa.Column("start_date",       sa.Date(), nullable=True),
        sa.Column("end_date",         sa.Date(), nullable=True),
        sa.Column("notes",            sa.Text(), nullable=True),
        sa.Column("metadata",         JSONB(), nullable=True),
        sa.Column("created_at",       sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",       sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Royalty billings ───────────────────────────────────────────────────────
    op.create_table(
        "royalty_billings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agreement_id",      UUID(as_uuid=True), sa.ForeignKey("franchise_agreements.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("franchisor_org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("franchisee_org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("period",            sa.String(7), nullable=False),   # YYYY-MM or YYYY-Q1
        sa.Column("revenue_basis",     sa.Numeric(16, 2), nullable=True),   # reported franchisee revenue
        sa.Column("royalty_amount",    sa.Numeric(14, 2), nullable=False),
        sa.Column("currency",          sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("status",            sa.String(20), nullable=False, server_default="draft"),  # draft|sent|paid|overdue
        sa.Column("invoice_id",        UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("due_date",          sa.Date(), nullable=True),
        sa.Column("paid_at",           sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Franchise catalog push log ─────────────────────────────────────────────
    op.create_table(
        "franchise_catalog_pushes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("franchisor_org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("franchisee_org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("product_ids",       JSONB(), nullable=False),   # list of product UUIDs pushed
        sa.Column("pushed_count",      sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_count",     sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count",     sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status",            sa.String(20), nullable=False, server_default="completed"),
        sa.Column("error_detail",      sa.Text(), nullable=True),
        sa.Column("created_at",        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("franchise_catalog_pushes")
    op.drop_table("royalty_billings")
    op.drop_table("franchise_agreements")
    op.drop_table("elimination_entries")
    op.drop_table("intercompany_transfers")
    op.drop_column("organizations", "reporting_currency")
    op.drop_column("organizations", "legal_name")
    op.drop_column("organizations", "entity_type")
    op.drop_column("organizations", "parent_org_id")
