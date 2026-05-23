"""Timesheet approval workflow.

Revision ID: kk1ll2mm3nn4
Revises: jj0kk1ll2mm3
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "kk1ll2mm3nn4"
down_revision = "jj0kk1ll2mm3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # timesheets — one row per staff per week
    op.create_table(
        "timesheets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_id", UUID(as_uuid=True), sa.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week_start", sa.Date, nullable=False),  # always Monday
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        # computed totals (denormalised for fast reads)
        sa.Column("total_hours", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("regular_hours", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("overtime_hours", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Numeric(12, 2), nullable=True),
        # workflow fields
        sa.Column("manager_comment", sa.Text, nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", UUID(as_uuid=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_id", "staff_id", "week_start", name="uq_timesheets_staff_week"),
    )
    op.create_index("ix_timesheets_org_id", "timesheets", ["org_id"])
    op.create_index("ix_timesheets_staff_id", "timesheets", ["staff_id"])
    op.create_index("ix_timesheets_org_status", "timesheets", ["org_id", "status"])

    # timesheet_lines — one row per punch/day
    op.create_table(
        "timesheet_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("timesheet_id", UUID(as_uuid=True), sa.ForeignKey("timesheets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("punch_id", UUID(as_uuid=True), sa.ForeignKey("shift_punches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("work_date", sa.Date, nullable=False),
        sa.Column("clock_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clock_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hours_raw", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("hours_adjusted", sa.Numeric(5, 2), nullable=True),  # manager override
        sa.Column("adjustment_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_timesheet_lines_timesheet_id", "timesheet_lines", ["timesheet_id"])


def downgrade() -> None:
    op.drop_table("timesheet_lines")
    op.drop_table("timesheets")
