"""cash_flow_adjustments table

Revision ID: dd4ee5ff6gg7
Revises: cc3dd4ee5ff6
Create Date: 2026-04-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "dd4ee5ff6gg7"
down_revision = "cc3dd4ee5ff6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cash_flow_adjustments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("adjustment_date", sa.Date, nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_by_staff_id", UUID(as_uuid=True), sa.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_cfa_org_date", "cash_flow_adjustments", ["org_id", "adjustment_date"])
    op.create_index("ix_cfa_org_id", "cash_flow_adjustments", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_cfa_org_date", "cash_flow_adjustments")
    op.drop_index("ix_cfa_org_id", "cash_flow_adjustments")
    op.drop_table("cash_flow_adjustments")
