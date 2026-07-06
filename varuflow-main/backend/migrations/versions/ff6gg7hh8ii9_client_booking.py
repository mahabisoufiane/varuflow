"""Client-perspective booking and self-service features.

Revision ID: ff6gg7hh8ii9
Revises:     ee5ff6gg7hh8
Create Date: 2026-05-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "ff6gg7hh8ii9"
down_revision = "ee5ff6gg7hh8"
branch_labels = None
# FKs to `appointments` and `services` (created on a parallel branch,
# e8f0a2b4c6d9). Force that migration first so a fresh `alembic upgrade head`
# can't order these tables before their FK targets exist.
depends_on = "e8f0a2b4c6d9"


def upgrade() -> None:
    # ── family_groups ────────────────────────────────────────────────────────────
    op.create_table(
        "family_groups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("primary_customer_id", UUID(as_uuid=True),
                  sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("shared_loyalty", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_family_groups_org_id", "family_groups", ["org_id"])
    op.create_index("ix_family_groups_primary_customer_id",
                    "family_groups", ["primary_customer_id"])

    op.create_table(
        "family_members",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("family_group_id", UUID(as_uuid=True),
                  sa.ForeignKey("family_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True),
                  sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("relationship", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_family_members_family_group_id", "family_members", ["family_group_id"])

    # ── booking_subscriptions ────────────────────────────────────────────────────
    op.create_table(
        "booking_subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True),
                  sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_id", UUID(as_uuid=True),
                  sa.ForeignKey("services.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_id", UUID(as_uuid=True), nullable=True),
        sa.Column("day_of_week", sa.Integer(), nullable=False),  # 0=Mon, 6=Sun
        sa.Column("start_time", sa.String(8), nullable=False),   # "HH:MM"
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False, server_default="weekly"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("last_booked_date", sa.Date(), nullable=True),
        sa.Column("next_booking_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_booking_subscriptions_org_id", "booking_subscriptions", ["org_id"])
    op.create_index("ix_booking_subscriptions_customer_id",
                    "booking_subscriptions", ["customer_id"])
    op.create_index("ix_booking_subscriptions_next_date",
                    "booking_subscriptions", ["next_booking_date"])

    # ── group_bookings ───────────────────────────────────────────────────────────
    op.create_table(
        "group_bookings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_customer_id", UUID(as_uuid=True),
                  sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_id", UUID(as_uuid=True),
                  sa.ForeignKey("services.id", ondelete="CASCADE"), nullable=False),
        sa.Column("appointment_id", UUID(as_uuid=True),
                  sa.ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(300), nullable=True),
        sa.Column("party_size", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("split_payment", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_group_bookings_org_id", "group_bookings", ["org_id"])
    op.create_index("ix_group_bookings_lead_customer_id",
                    "group_bookings", ["lead_customer_id"])

    op.create_table(
        "group_booking_participants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("group_booking_id", UUID(as_uuid=True),
                  sa.ForeignKey("group_bookings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True),
                  sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("amount_due", sa.Numeric(14, 2), nullable=True),
        sa.Column("paid", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_group_booking_participants_booking_id",
                    "group_booking_participants", ["group_booking_id"])

    # ── booking_waitlist ─────────────────────────────────────────────────────────
    op.create_table(
        "booking_waitlist",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True),
                  sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_id", UUID(as_uuid=True),
                  sa.ForeignKey("services.id", ondelete="CASCADE"), nullable=True),
        sa.Column("staff_id", UUID(as_uuid=True), nullable=True),
        sa.Column("preferred_date", sa.Date(), nullable=True),
        sa.Column("preferred_time_from", sa.String(8), nullable=True),
        sa.Column("preferred_time_to", sa.String(8), nullable=True),
        sa.Column("flexibility_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="waiting"),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("offer_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("offered_appointment_id", UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_booking_waitlist_org_id", "booking_waitlist", ["org_id"])
    op.create_index("ix_booking_waitlist_customer_id", "booking_waitlist", ["customer_id"])
    op.create_index("ix_booking_waitlist_service_id", "booking_waitlist", ["service_id"])

    # ── wallet_passes ────────────────────────────────────────────────────────────
    op.create_table(
        "wallet_passes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True),
                  sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pass_type", sa.String(20), nullable=False, server_default="loyalty"),
        sa.Column("platform", sa.String(20), nullable=False),  # apple / google
        sa.Column("serial_number", sa.String(100), nullable=False, unique=True),
        sa.Column("barcode_value", sa.String(200), nullable=True),
        sa.Column("points_balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tier", sa.String(50), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_wallet_passes_org_id", "wallet_passes", ["org_id"])
    op.create_index("ix_wallet_passes_customer_id", "wallet_passes", ["customer_id"])
    op.create_index("ix_wallet_passes_serial_number",
                    "wallet_passes", ["serial_number"], unique=True)

    # ── customer_app_push_tokens ─────────────────────────────────────────────────
    op.create_table(
        "customer_app_push_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True),
                  sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(500), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),  # ios / android / web
        sa.Column("app_version", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("customer_id", "token", name="uq_customer_app_push_token"),
    )
    op.create_index("ix_customer_app_push_tokens_org_id",
                    "customer_app_push_tokens", ["org_id"])
    op.create_index("ix_customer_app_push_tokens_customer_id",
                    "customer_app_push_tokens", ["customer_id"])

    # ── customer_app_config ──────────────────────────────────────────────────────
    op.create_table(
        "customer_app_config",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("app_name", sa.String(100), nullable=False),
        sa.Column("primary_color", sa.String(7), nullable=False, server_default="#1a2332"),
        sa.Column("secondary_color", sa.String(7), nullable=False, server_default="#ffffff"),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("welcome_message", sa.Text(), nullable=True),
        sa.Column("features_enabled", JSONB(), nullable=True),
        sa.Column("booking_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("loyalty_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_customer_app_config_org_id", "customer_app_config", ["org_id"])


def downgrade() -> None:
    op.drop_table("customer_app_config")
    op.drop_table("customer_app_push_tokens")
    op.drop_table("wallet_passes")
    op.drop_table("booking_waitlist")
    op.drop_table("group_booking_participants")
    op.drop_table("group_bookings")
    op.drop_table("booking_subscriptions")
    op.drop_table("family_members")
    op.drop_table("family_groups")
