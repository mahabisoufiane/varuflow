"""v47 — Salon & Spa booking module (Item 31)

Revision ID: e8f0a2b4c6d9
Revises: d7e9f1a3b5c7
Create Date: 2026-04-23

Note on the number
------------------
The Item-31 spec reserved ``v39`` for this migration, but v39 was already
consumed by Item 17 (recurring invoice auto-send) long before the booking
module was prioritised. To keep the Alembic chain strictly linear and
avoid rewriting three intermediate migrations, the module lands at v47 —
the next slot after v46 (PII widen). The spec deviation is documented in
PROJECT_CONTENTS.md §60 so a future auditor sees it was deliberate, not
a renumber accident.

Adds four new tables (services, staff, appointments, appointment_reminders)
and three columns on ``organizations`` for the MENA-specific flags
(female-only mode, prayer-time blocking, prayer-time schedule JSON).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e8f0a2b4c6d9"
down_revision = "d7e9f1a3b5c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── organizations: MENA-specific booking flags ─────────────────────
    op.add_column(
        "organizations",
        sa.Column(
            "booking_female_only_mode",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "booking_prayer_time_blocking_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    # JSONB array of {"name": "Dhuhr", "start": "12:15", "duration_minutes": 20}
    # evaluated in the org's local timezone. NULL = no prayer windows.
    op.add_column(
        "organizations",
        sa.Column("booking_prayer_times", postgresql.JSONB(), nullable=True),
    )

    # ── staff ──────────────────────────────────────────────────────────
    # Created BEFORE services so the ``services.staff_id`` FK resolves
    # in a single DDL pass. A forward-reference would force an extra
    # ALTER TABLE which is more churn than ordering the create_table
    # calls by dependency.
    op.create_table(
        "staff",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(64), nullable=True),
        # {"mon": [{"start": "09:00", "end": "18:00"}], "tue": [...], ...}
        sa.Column("working_hours", postgresql.JSONB(), nullable=True),
        # [{"start": "12:00", "end": "13:00", "label": "lunch"}, ...]
        sa.Column("break_times", postgresql.JSONB(), nullable=True),
        # ["hair_colour", "keratin"] — used for female-only mode matching
        sa.Column("specialties", postgresql.JSONB(), nullable=True),
        # MENA: female-only salons need to surface only female staff.
        sa.Column("gender", sa.String(16), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── services ───────────────────────────────────────────────────────
    op.create_table(
        "services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column(
            "staff_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("staff.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── appointments ───────────────────────────────────────────────────
    op.create_table(
        "appointments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "service_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("services.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "staff_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("staff.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "warehouse_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'booked'"),
        ),
        sa.Column(
            "channel",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'web'"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "loyalty_points_awarded",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Composite index: per-staff per-day slot lookups are the hot path.
    op.create_index(
        "ix_appointments_staff_start",
        "appointments",
        ["staff_id", "start_time"],
    )

    # ── appointment_reminders ─────────────────────────────────────────
    op.create_table(
        "appointment_reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "appointment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("appointments.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("type", sa.String(16), nullable=False),  # sms / whatsapp / email
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'pending'"),  # pending / sent / failed / skipped
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("appointment_reminders")
    op.drop_index("ix_appointments_staff_start", table_name="appointments")
    op.drop_table("appointments")
    op.drop_table("services")  # has FK to staff — drop first
    op.drop_table("staff")
    op.drop_column("organizations", "booking_prayer_times")
    op.drop_column("organizations", "booking_prayer_time_blocking_enabled")
    op.drop_column("organizations", "booking_female_only_mode")
