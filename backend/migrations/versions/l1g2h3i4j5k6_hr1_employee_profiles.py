"""hr1 — employee_profiles and employee_emergency_contacts

Revision ID: l1g2h3i4j5k6
Revises:     k0f1g2h3i4j5
Create Date: 2026-04-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "l1g2h3i4j5k6"
down_revision = "k0f1g2h3i4j5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employee_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("reports_to_staff_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_title", sa.String(120), nullable=True),
        sa.Column("employment_type", sa.String(20), nullable=False, server_default="full_time"),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("national_id", sa.String(255), nullable=True),
        sa.Column("bank_account", sa.String(255), nullable=True),
        sa.Column("bank_name", sa.String(120), nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_employee_profiles_org_id", "employee_profiles", ["org_id"])
    op.create_index("ix_employee_profiles_staff_id", "employee_profiles", ["staff_id"])
    op.create_index("ix_employee_profiles_reports_to", "employee_profiles", ["reports_to_staff_id"])

    op.create_table(
        "employee_emergency_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("relationship", sa.String(60), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_employee_emergency_contacts_staff_id", "employee_emergency_contacts", ["staff_id"])
    op.create_index("ix_employee_emergency_contacts_org_id", "employee_emergency_contacts", ["org_id"])


def downgrade() -> None:
    op.drop_table("employee_emergency_contacts")
    op.drop_table("employee_profiles")
