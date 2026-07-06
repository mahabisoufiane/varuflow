"""Integrations Customers Expect + Quality of Life.

Revision ID: oo5pp6qq7rr8
Revises:     nn4oo5pp6qq7
Create Date: 2026-05-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "oo5pp6qq7rr8"
down_revision = "nn4oo5pp6qq7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Calendar Integrations ────────────────────────────────────────────────────

    op.create_table(
        "merchant_calendar_syncs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        # google / outlook / apple
        sa.Column("access_token", sa.Text(), nullable=True),
        # encrypted at application level
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("calendar_id", sa.String(200), nullable=True),
        sa.Column("sync_direction", sa.String(10), nullable=False, server_default="both"),
        # both / push / pull
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", "user_id", "provider",
                            name="uq_merchant_calendar_syncs_org_user_provider"),
    )
    op.create_index("ix_merchant_calendar_syncs_org_id",
                    "merchant_calendar_syncs", ["org_id"])
    op.create_index("ix_merchant_calendar_syncs_user_id",
                    "merchant_calendar_syncs", ["user_id"])

    # ── Zapier / Make Connector ─────────────────────────────────────────────────

    op.create_table(
        "zapier_hooks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("subscribe_url", sa.String(500), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        # booking.created / invoice.paid / customer.created / etc.
        sa.Column("hook_type", sa.String(10), nullable=False, server_default="zapier"),
        # zapier / make / generic
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_zapier_hooks_org_id", "zapier_hooks", ["org_id"])
    op.create_index("ix_zapier_hooks_event_type", "zapier_hooks", ["org_id", "event_type"])

    op.create_table(
        "zapier_event_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hook_id", UUID(as_uuid=True),
                  sa.ForeignKey("zapier_hooks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("payload", JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        # pending / delivered / failed / skipped
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_zapier_event_logs_org_id", "zapier_event_logs", ["org_id"])
    op.create_index("ix_zapier_event_logs_hook_id", "zapier_event_logs", ["hook_id"])
    op.create_index("ix_zapier_event_logs_status", "zapier_event_logs", ["org_id", "status"])

    # ── Customer Webhooks UI ────────────────────────────────────────────────────

    op.create_table(
        "customer_webhooks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("secret", sa.String(100), nullable=False),
        # HMAC-SHA256 signing secret — generated automatically
        sa.Column("events", JSONB(), nullable=False, server_default="[]"),
        # list of event type strings
        sa.Column("description", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_customer_webhooks_org_id", "customer_webhooks", ["org_id"])
    op.create_index("ix_customer_webhooks_customer_id",
                    "customer_webhooks", ["customer_id"])

    op.create_table(
        "customer_webhook_deliveries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("webhook_id", UUID(as_uuid=True),
                  sa.ForeignKey("customer_webhooks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("payload", JSONB(), nullable=False, server_default="{}"),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_customer_webhook_deliveries_webhook_id",
                    "customer_webhook_deliveries", ["webhook_id"])
    op.create_index("ix_customer_webhook_deliveries_org_id",
                    "customer_webhook_deliveries", ["org_id"])

    # ── Customer API Keys ───────────────────────────────────────────────────────

    op.create_table(
        "customer_api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("key_hash", sa.String(200), nullable=False),
        # bcrypt hash of the actual key — never store plaintext
        sa.Column("key_prefix", sa.String(12), nullable=False),
        # first 12 chars for display e.g. "vf_abcd1234"
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("scopes", JSONB(), nullable=False, server_default="[]"),
        # ["bookings:read", "invoices:read", ...]
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_customer_api_keys_org_id", "customer_api_keys", ["org_id"])
    op.create_index("ix_customer_api_keys_customer_id",
                    "customer_api_keys", ["customer_id"])
    op.create_index("ix_customer_api_keys_prefix", "customer_api_keys", ["key_prefix"])

    # ── Quality of Life ──────────────────────────────────────────────────────────

    op.create_table(
        "search_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("query", sa.String(200), nullable=False),
        sa.Column("result_type", sa.String(30), nullable=True),
        # customer / invoice / product / booking / etc.
        sa.Column("result_id", UUID(as_uuid=True), nullable=True),
        sa.Column("result_label", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_search_history_org_id", "search_history", ["org_id"])
    op.create_index("ix_search_history_user_id", "search_history", ["org_id", "user_id"])

    op.create_table(
        "notification_bundle_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("bundle_name", sa.String(100), nullable=False),
        sa.Column("event_types", JSONB(), nullable=False, server_default="[]"),
        sa.Column("delivery_channel", sa.String(20), nullable=False, server_default="email"),
        # push / email / sms / in_app
        sa.Column("schedule", sa.String(20), nullable=False, server_default="immediate"),
        # immediate / hourly / daily / weekly
        sa.Column("digest_time", sa.String(5), nullable=True),
        # HH:MM for daily/weekly digests
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", "user_id", "bundle_name",
                            name="uq_notification_bundle_configs_org_user_name"),
    )
    op.create_index("ix_notification_bundle_configs_org_id",
                    "notification_bundle_configs", ["org_id"])
    op.create_index("ix_notification_bundle_configs_user_id",
                    "notification_bundle_configs", ["user_id"])

    op.create_table(
        "org_location_timezones",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("location_name", sa.String(200), nullable=False),
        sa.Column("timezone", sa.String(50), nullable=False),
        # IANA timezone string e.g. "Europe/Stockholm"
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", "location_name",
                            name="uq_org_location_timezones_org_name"),
    )
    op.create_index("ix_org_location_timezones_org_id",
                    "org_location_timezones", ["org_id"])


def downgrade() -> None:
    op.drop_table("org_location_timezones")
    op.drop_table("notification_bundle_configs")
    op.drop_table("search_history")
    op.drop_table("customer_api_keys")
    op.drop_table("customer_webhook_deliveries")
    op.drop_table("customer_webhooks")
    op.drop_table("zapier_event_logs")
    op.drop_table("zapier_hooks")
    op.drop_table("merchant_calendar_syncs")
