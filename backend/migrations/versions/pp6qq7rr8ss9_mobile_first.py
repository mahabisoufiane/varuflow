"""Mobile-First Features.

Revision ID: pp6qq7rr8ss9
Revises:     oo5pp6qq7rr8
Create Date: 2026-05-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "pp6qq7rr8ss9"
down_revision = "oo5pp6qq7rr8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Home Screen / Lock Screen Widgets ───────────────────────────────────────

    op.create_table(
        "home_screen_widgets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("widget_type", sa.String(40), nullable=False),
        # today_bookings / today_revenue / low_stock / lock_screen_alerts
        sa.Column("platform", sa.String(10), nullable=False),
        # ios / android
        sa.Column("widget_size", sa.String(10), nullable=False, server_default="medium"),
        # small / medium / large
        sa.Column("config", JSONB(), nullable=False, server_default="'{}'"),
        # per-widget config: refresh_interval, thresholds, layout preferences
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_rendered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", "user_id", "widget_type", "platform",
                            name="uq_home_screen_widgets_org_user_type_platform"),
    )
    op.create_index("ix_home_screen_widgets_org_id", "home_screen_widgets", ["org_id"])
    op.create_index("ix_home_screen_widgets_user_id", "home_screen_widgets", ["user_id"])

    op.create_table(
        "widget_data_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("widget_type", sa.String(40), nullable=False),
        sa.Column("snapshot", JSONB(), nullable=False, server_default="'{}'"),
        # serialized widget payload served to the native app/widget extension
        sa.Column("generated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "widget_type",
                            name="uq_widget_data_snapshots_org_type"),
    )
    op.create_index("ix_widget_data_snapshots_org_id", "widget_data_snapshots", ["org_id"])
    op.create_index("ix_widget_data_snapshots_expires",
                    "widget_data_snapshots", ["org_id", "expires_at"])

    # ── Apple Watch / Wear OS Sessions ──────────────────────────────────────────

    op.create_table(
        "watch_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(10), nullable=False),
        # apple_watch / wear_os
        sa.Column("device_id", sa.String(200), nullable=False),
        sa.Column("session_token_hash", sa.String(200), nullable=False),
        # hashed for security — issued by phone app companion
        sa.Column("paired_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.UniqueConstraint("org_id", "user_id", "device_id",
                            name="uq_watch_sessions_org_user_device"),
    )
    op.create_index("ix_watch_sessions_org_id", "watch_sessions", ["org_id"])
    op.create_index("ix_watch_sessions_user_id", "watch_sessions", ["user_id"])

    # ── Siri Shortcuts / Google Assistant ───────────────────────────────────────

    op.create_table(
        "voice_shortcuts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(15), nullable=False),
        # siri / google_assistant / bixby
        sa.Column("phrase", sa.String(200), nullable=False),
        # e.g. "Show today's revenue"
        sa.Column("action_type", sa.String(40), nullable=False),
        # today_revenue / today_bookings / low_stock / open_invoices / next_appointment
        sa.Column("action_params", JSONB(), nullable=False, server_default="'{}'"),
        # extra params, e.g. {"date_range": "today", "currency": "SEK"}
        sa.Column("response_template", sa.String(500), nullable=True),
        # optional custom spoken response template
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trigger_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_voice_shortcuts_org_id", "voice_shortcuts", ["org_id"])
    op.create_index("ix_voice_shortcuts_user_id", "voice_shortcuts", ["org_id", "user_id"])

    # ── Lock Screen Alerts ───────────────────────────────────────────────────────

    op.create_table(
        "lock_screen_alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("alert_type", sa.String(40), nullable=False),
        # low_stock / overdue_invoice / booking_conflict / cash_flow_warning / payment_received
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False, server_default="info"),
        # info / warning / critical
        sa.Column("deep_link", sa.String(300), nullable=True),
        # e.g. "varuflow://invoices/abc123"
        sa.Column("reference_id", UUID(as_uuid=True), nullable=True),
        sa.Column("reference_type", sa.String(40), nullable=True),
        # invoice / product / booking / etc.
        sa.Column("is_dismissed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_lock_screen_alerts_org_id", "lock_screen_alerts", ["org_id"])
    op.create_index("ix_lock_screen_alerts_user_id", "lock_screen_alerts", ["org_id", "user_id"])
    op.create_index("ix_lock_screen_alerts_active",
                    "lock_screen_alerts", ["org_id", "user_id", "is_dismissed"])


def downgrade() -> None:
    op.drop_table("lock_screen_alerts")
    op.drop_table("voice_shortcuts")
    op.drop_table("watch_sessions")
    op.drop_table("widget_data_snapshots")
    op.drop_table("home_screen_widgets")
