"""v66 — Staff availability overrides (Item 57).

The ``staff`` table already carries a JSONB ``working_hours`` column
for the baseline weekly schedule. This migration adds a per-date
override table: PTO, sick leave, extra shifts, holidays. The booking
slot resolver consults both sources — weekly baseline minus
override.

Each row blocks (or grants) a contiguous ``[start_at, end_at)``
window for a given staff member. Rows are org-scoped for tenant
isolation and indexed by ``(org_id, staff_id, start_at)`` so
"availability on day D" is a single range scan.

Revision: b6d8f0a2c4e7
Revises:  a5c7e9b1d3f6 (v65 — product waitlist, Item 56)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b6d8f0a2c4e7"
down_revision = "a5c7e9b1d3f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staff_availability_overrides",
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
        # kind ∈ {time_off, sick, extra_shift, holiday}
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "end_at > start_at",
            name="ck_staff_availability_range",
        ),
    )
    op.create_index(
        "ix_staff_availability_org_staff_start",
        "staff_availability_overrides",
        ["org_id", "staff_id", "start_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_staff_availability_org_staff_start",
        table_name="staff_availability_overrides",
    )
    op.drop_table("staff_availability_overrides")
