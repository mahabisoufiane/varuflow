"""leave management v2 — entitlements, public holidays

Revision ID: ii9jj0kk1ll2
Revises: hh8ii9jj0kk1
Create Date: 2026-04-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "ii9jj0kk1ll2"
down_revision = "hh8ii9jj0kk1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # leave_requests: store requester email for notifications
    op.add_column("leave_requests", sa.Column("requester_email", sa.String(254), nullable=True))
    op.add_column("leave_requests", sa.Column("reviewer_note", sa.Text, nullable=True))

    # leave_entitlements — annual allocation per staff member per leave type
    op.create_table(
        "leave_entitlements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_id", UUID(as_uuid=True), nullable=False),
        sa.Column("leave_type", sa.String(20), nullable=False),     # annual | sick | parental | unpaid
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("days_allocated", sa.Numeric(5, 1), nullable=False, server_default="0"),
        sa.Column("carry_over_days", sa.Numeric(5, 1), nullable=False, server_default="0"),
        sa.Column("carry_over_cap", sa.Numeric(5, 1), nullable=True),  # NULL = uncapped
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_leave_entitlements_org_id", "leave_entitlements", ["org_id"])
    op.create_index("ix_leave_entitlements_staff_year", "leave_entitlements", ["org_id", "staff_id", "year"])
    op.create_unique_constraint(
        "uq_leave_entitlements_staff_type_year",
        "leave_entitlements",
        ["staff_id", "leave_type", "year"],
    )

    # public_holidays — country-level holiday calendar
    op.create_table(
        "public_holidays",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),   # SE | AE | SA | MA
        sa.Column("holiday_date", sa.Date, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
    )
    op.create_index("ix_public_holidays_org_country_year", "public_holidays", ["org_id", "country_code", "year"])
    op.create_unique_constraint(
        "uq_public_holidays_org_country_date",
        "public_holidays",
        ["org_id", "country_code", "holiday_date"],
    )


def downgrade() -> None:
    op.drop_table("public_holidays")
    op.drop_table("leave_entitlements")
    op.drop_column("leave_requests", "reviewer_note")
    op.drop_column("leave_requests", "requester_email")
