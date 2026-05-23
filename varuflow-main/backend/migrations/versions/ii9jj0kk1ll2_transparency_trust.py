"""Transparency & Trust — Live Status, Timeline, Tracking, Photos, History.

Revision ID: ii9jj0kk1ll2
Revises:     hh8ii9jj0kk1
Create Date: 2026-05-01
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
    # ── service_status_alerts ────────────────────────────────────────────────────
    op.create_table(
        "service_status_alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("appointment_id", UUID(as_uuid=True), nullable=True),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=True),
        sa.Column("staff_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("alert_type", sa.String(50), nullable=False),
        # running_late / cancelled / rescheduled / ready / completed / custom
        sa.Column("delay_minutes", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("push_sent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("push_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_service_status_alerts_org_id", "service_status_alerts", ["org_id"])
    op.create_index("ix_service_status_alerts_appointment_id",
                    "service_status_alerts", ["appointment_id"])
    op.create_index("ix_service_status_alerts_customer_id",
                    "service_status_alerts", ["customer_id"])

    # ── service_timelines ────────────────────────────────────────────────────────
    op.create_table(
        "service_timelines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("appointment_id", UUID(as_uuid=True), nullable=True),
        sa.Column("order_id", UUID(as_uuid=True), nullable=True),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_service_timelines_org_id", "service_timelines", ["org_id"])
    op.create_index("ix_service_timelines_appointment_id",
                    "service_timelines", ["appointment_id"])

    op.create_table(
        "service_timeline_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("timeline_id", UUID(as_uuid=True),
                  sa.ForeignKey("service_timelines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage", sa.String(100), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        # pending / in_progress / completed / skipped
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_service_timeline_events_timeline_id",
                    "service_timeline_events", ["timeline_id"])

    # ── live_tracking_sessions ───────────────────────────────────────────────────
    op.create_table(
        "live_tracking_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("appointment_id", UUID(as_uuid=True), nullable=True),
        sa.Column("staff_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=True),
        sa.Column("share_token", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        # active / ended
        sa.Column("current_lat", sa.Numeric(10, 7), nullable=True),
        sa.Column("current_lng", sa.Numeric(10, 7), nullable=True),
        sa.Column("eta_minutes", sa.Integer(), nullable=True),
        sa.Column("destination_lat", sa.Numeric(10, 7), nullable=True),
        sa.Column("destination_lng", sa.Numeric(10, 7), nullable=True),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_live_tracking_sessions_org_id", "live_tracking_sessions", ["org_id"])
    op.create_index("ix_live_tracking_sessions_token",
                    "live_tracking_sessions", ["share_token"], unique=True)

    # ── service_photo_updates ────────────────────────────────────────────────────
    op.create_table(
        "service_photo_updates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("appointment_id", UUID(as_uuid=True), nullable=True),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=True),
        sa.Column("sent_by", UUID(as_uuid=True), nullable=True),
        sa.Column("photo_url", sa.Text(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("is_viewed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_service_photo_updates_org_id", "service_photo_updates", ["org_id"])
    op.create_index("ix_service_photo_updates_appointment_id",
                    "service_photo_updates", ["appointment_id"])
    op.create_index("ix_service_photo_updates_customer_id",
                    "service_photo_updates", ["customer_id"])

    # ── customer_history_events ──────────────────────────────────────────────────
    op.create_table(
        "customer_history_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        # appointment / purchase / invoice / message / review / loyalty_earn /
        # loyalty_redeem / note / photo
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reference_id", UUID(as_uuid=True), nullable=True),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_customer_history_events_org_id",
                    "customer_history_events", ["org_id"])
    op.create_index("ix_customer_history_events_customer_id",
                    "customer_history_events", ["customer_id"])
    op.create_index("ix_customer_history_events_event_date",
                    "customer_history_events", ["event_date"])


def downgrade() -> None:
    op.drop_table("customer_history_events")
    op.drop_table("service_photo_updates")
    op.drop_table("live_tracking_sessions")
    op.drop_table("service_timeline_events")
    op.drop_table("service_timelines")
    op.drop_table("service_status_alerts")
