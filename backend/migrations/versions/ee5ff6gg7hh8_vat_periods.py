"""vat_periods — submission status tracking

Revision ID: ee5ff6gg7hh8
Revises: dd4ee5ff6gg7
Create Date: 2026-04-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "ee5ff6gg7hh8"
down_revision = "dd4ee5ff6gg7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vat_periods",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("country", sa.String(5), nullable=False),           # SE | NO | AE | GCC
        sa.Column("from_date", sa.Date, nullable=False),
        sa.Column("to_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="UNFILED"),  # UNFILED | FILED
        sa.Column("net_vat_payable", sa.Numeric(14, 2), nullable=False),
        sa.Column("snapshot_json", sa.Text, nullable=True),           # full boxes JSON at time of lock
        sa.Column("filed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("filed_by_staff_id", UUID(as_uuid=True), sa.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reference", sa.String(200), nullable=True),        # official submission reference
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_vat_periods_org_country", "vat_periods", ["org_id", "country"])
    op.create_index("ix_vat_periods_org_dates", "vat_periods", ["org_id", "from_date", "to_date"])
    op.create_unique_constraint("uq_vat_period_org_country_dates", "vat_periods", ["org_id", "country", "from_date", "to_date"])


def downgrade() -> None:
    op.drop_constraint("uq_vat_period_org_country_dates", "vat_periods")
    op.drop_index("ix_vat_periods_org_dates", "vat_periods")
    op.drop_index("ix_vat_periods_org_country", "vat_periods")
    op.drop_table("vat_periods")
