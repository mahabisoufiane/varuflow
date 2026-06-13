"""Org setup fields, import jobs, and sandbox flag.

Revision ID: aa1bb2cc3dd4
Revises: oo6pp7qq8rr9
Create Date: 2026-05-01

Adds:
  • organizations.fiscal_year_start  INT (month 1–12, default 1 = January)
  • organizations.is_sandbox          BOOL (pre-populated demo org)
  • organizations.onboarding_wizard_completed  BOOL
  • Table import_jobs — tracks CSV/XLSX data migration jobs
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "aa1bb2cc3dd4"
down_revision = "oo6pp7qq8rr9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── organizations additions ───────────────────────────────────────────────
    op.add_column(
        "organizations",
        sa.Column("fiscal_year_start", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "organizations",
        sa.Column("is_sandbox", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "organizations",
        sa.Column("onboarding_wizard_completed", sa.Boolean(), nullable=False, server_default="false"),
    )

    # ── import_jobs ────────────────────────────────────────────────────────────
    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        # customers | products | invoices | suppliers | chart_of_accounts | inventory
        sa.Column("import_type", sa.String(30), nullable=False),
        # pending | validating | ready | importing | done | failed
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("filename", sa.String(500), nullable=True),
        sa.Column("source_system", sa.String(50), nullable=True),  # quickbooks/xero/fortnox/sage/visma/csv
        sa.Column("total_rows", sa.Integer(), nullable=True),
        sa.Column("imported_rows", sa.Integer(), nullable=True),
        sa.Column("failed_rows", sa.Integer(), nullable=True),
        sa.Column("column_mapping", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("validation_errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("import_jobs")
    op.drop_column("organizations", "onboarding_wizard_completed")
    op.drop_column("organizations", "is_sandbox")
    op.drop_column("organizations", "fiscal_year_start")
