"""v75 — Shift management (Item 67).

Operators schedule staff shifts, staff clock-in/out against them,
and payroll exports aggregate hours per staff for a pay period.

Two tables:
* ``shifts`` — planned shift slot (staff, start, end, optional notes).
* ``shift_punches`` — clock-in / clock-out events against a shift.

Shifts are unique per ``(staff_id, start_at)`` — operators can't
accidentally double-book the same start slot; overlapping shifts
with different start times are allowed (handled by the service
layer's ``detect_overlap``).

Revision: e6f8a0b2c5d6
Revises:  d5e7f9a1b4c5 (v74 — customer contracts, Item 66)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e6f8a0b2c5d6"
down_revision = "d5e7f9a1b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shifts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "staff_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("staff.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at",   sa.DateTime(timezone=True), nullable=False),
        # Optional hourly rate snapshot — lets payroll compute gross
        # pay without re-reading the staff row at export time.
        sa.Column("hourly_rate", sa.Numeric(10, 2), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "staff_id", "start_at", name="uq_shifts_staff_start"
        ),
    )
    op.create_index("ix_shifts_org", "shifts", ["org_id"])
    op.create_index(
        "ix_shifts_org_start", "shifts", ["org_id", "start_at"],
    )

    op.create_table(
        "shift_punches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "shift_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("shifts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "staff_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("staff.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("clock_in_at",  sa.DateTime(timezone=True), nullable=False),
        sa.Column("clock_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_shift_punches_shift", "shift_punches", ["shift_id"],
    )
    op.create_index(
        "ix_shift_punches_staff", "shift_punches", ["staff_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_shift_punches_staff", table_name="shift_punches")
    op.drop_index("ix_shift_punches_shift", table_name="shift_punches")
    op.drop_table("shift_punches")
    op.drop_index("ix_shifts_org_start", table_name="shifts")
    op.drop_index("ix_shifts_org", table_name="shifts")
    op.drop_table("shifts")
