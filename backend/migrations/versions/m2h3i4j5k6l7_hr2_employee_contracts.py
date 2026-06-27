"""hr2 — employee_contracts

Revision ID: m2h3i4j5k6l7
Revises:     l1g2h3i4j5k6
Create Date: 2026-04-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "m2h3i4j5k6l7"
down_revision = "l1g2h3i4j5k6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employee_contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contract_type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("salary", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("hours_per_week", sa.Numeric(5, 2), nullable=True),
        sa.Column("file_url", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_employee_contracts_org_id", "employee_contracts", ["org_id"])
    op.create_index("ix_employee_contracts_staff_id", "employee_contracts", ["staff_id"])


def downgrade() -> None:
    op.drop_table("employee_contracts")
