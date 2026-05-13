"""hr profiles v2 — full_legal_name, date_of_birth, department, status; contract probation/notice

Revision ID: hh8ii9jj0kk1
Revises: gg7hh8ii9jj0
Create Date: 2026-04-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "hh8ii9jj0kk1"
down_revision = "gg7hh8ii9jj0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # employee_profiles: legal name, DOB, department, employment status
    op.add_column("employee_profiles", sa.Column("full_legal_name", sa.String(200), nullable=True))
    op.add_column("employee_profiles", sa.Column("date_of_birth", sa.Date, nullable=True))
    op.add_column("employee_profiles", sa.Column("department", sa.String(100), nullable=True))
    op.add_column(
        "employee_profiles",
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
    )
    op.create_index("ix_employee_profiles_department", "employee_profiles", ["org_id", "department"])
    op.create_index("ix_employee_profiles_status", "employee_profiles", ["org_id", "status"])

    # employee_contracts: probation end date, notice period in days
    op.add_column("employee_contracts", sa.Column("probation_end_date", sa.Date, nullable=True))
    op.add_column("employee_contracts", sa.Column("notice_period_days", sa.Integer, nullable=True))


def downgrade() -> None:
    op.drop_column("employee_contracts", "notice_period_days")
    op.drop_column("employee_contracts", "probation_end_date")
    op.drop_index("ix_employee_profiles_status", "employee_profiles")
    op.drop_index("ix_employee_profiles_department", "employee_profiles")
    op.drop_column("employee_profiles", "status")
    op.drop_column("employee_profiles", "department")
    op.drop_column("employee_profiles", "date_of_birth")
    op.drop_column("employee_profiles", "full_legal_name")
