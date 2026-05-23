"""Reporting + AI Across the Stack.

Revision ID: nn4oo5pp6qq7
Revises:     mm3nn4oo5pp6
Create Date: 2026-05-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "nn4oo5pp6qq7"
down_revision = "mm3nn4oo5pp6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Reporting ────────────────────────────────────────────────────────────────

    op.create_table(
        "statement_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by", sa.String(20), nullable=False, server_default="customer"),
        # customer / staff
        sa.Column("date_from", sa.Date(), nullable=True),
        sa.Column("date_to", sa.Date(), nullable=True),
        sa.Column("format", sa.String(10), nullable=False, server_default="pdf"),
        # pdf / csv / json
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        # pending / generating / ready / failed
        sa.Column("file_url", sa.String(500), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_statement_requests_org_id", "statement_requests", ["org_id"])
    op.create_index("ix_statement_requests_customer_id",
                    "statement_requests", ["customer_id"])

    op.create_table(
        "mobile_kpi_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("kpi_ids", JSONB(), nullable=False, server_default="'[]'"),
        # ordered list of KPI keys to display
        sa.Column("notification_deep_links_enabled", sa.Boolean(),
                  nullable=False, server_default="true"),
        sa.Column("refresh_interval_minutes", sa.Integer(),
                  nullable=False, server_default="15"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", "user_id", name="uq_mobile_kpi_configs_org_user"),
    )
    op.create_index("ix_mobile_kpi_configs_org_id", "mobile_kpi_configs", ["org_id"])

    op.create_table(
        "push_notification_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("token", sa.String(500), nullable=False),
        sa.Column("platform", sa.String(10), nullable=False, server_default="web"),
        # ios / android / web
        sa.Column("device_label", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", "user_id", "token",
                            name="uq_push_notification_tokens_org_user_token"),
    )
    op.create_index("ix_push_notification_tokens_org_id",
                    "push_notification_tokens", ["org_id"])
    op.create_index("ix_push_notification_tokens_user_id",
                    "push_notification_tokens", ["user_id"])

    op.create_table(
        "voice_report_queries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("parsed_intent", JSONB(), nullable=True),
        # {metric: "revenue", period: "this_month", ...}
        sa.Column("result_text", sa.Text(), nullable=True),
        sa.Column("result_data", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_voice_report_queries_org_id", "voice_report_queries", ["org_id"])
    op.create_index("ix_voice_report_queries_user_id", "voice_report_queries", ["user_id"])

    op.create_table(
        "anomaly_notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(40), nullable=False),
        # huge_sale / refund_spike / system_error / unusual_login
        # inventory_low / payment_failed / churn_risk / upsell_opportunity
        sa.Column("severity", sa.String(10), nullable=False, server_default="info"),
        # info / warning / critical
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("reference_id", UUID(as_uuid=True), nullable=True),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("pushed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_anomaly_notifications_org_id", "anomaly_notifications", ["org_id"])
    op.create_index("ix_anomaly_notifications_severity",
                    "anomaly_notifications", ["org_id", "severity"])
    op.create_index("ix_anomaly_notifications_is_read",
                    "anomaly_notifications", ["org_id", "is_read"])

    # ── AI Across the Stack ─────────────────────────────────────────────────────

    op.create_table(
        "ai_product_descriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True),
                  sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("prompt_context", JSONB(), nullable=False, server_default="'{}'"),
        # {name, category, features: [], tone: "professional"}
        sa.Column("generated_text", sa.Text(), nullable=False),
        sa.Column("model_used", sa.String(50), nullable=False, server_default="gpt-4o"),
        sa.Column("accepted", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_ai_product_descriptions_org_id",
                    "ai_product_descriptions", ["org_id"])
    op.create_index("ix_ai_product_descriptions_product_id",
                    "ai_product_descriptions", ["product_id"])

    op.create_table(
        "ai_email_drafts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", UUID(as_uuid=True),
                  sa.ForeignKey("unified_messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("thread_id", UUID(as_uuid=True),
                  sa.ForeignKey("unified_inbox_threads.id", ondelete="SET NULL"), nullable=True),
        sa.Column("prompt_context", JSONB(), nullable=False, server_default="'{}'"),
        # {original_message, tone_sample, merchant_name}
        sa.Column("draft_text", sa.Text(), nullable=False),
        sa.Column("model_used", sa.String(50), nullable=False, server_default="gpt-4o"),
        sa.Column("tone", sa.String(20), nullable=True),
        sa.Column("accepted", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_ai_email_drafts_org_id", "ai_email_drafts", ["org_id"])
    op.create_index("ix_ai_email_drafts_message_id", "ai_email_drafts", ["message_id"])

    op.create_table(
        "ai_photo_tags",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True),
                  sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("photo_url", sa.String(500), nullable=False),
        sa.Column("tags", JSONB(), nullable=False, server_default="'[]'"),
        # [{tag: "blue", confidence: 0.92, category: "color"}, ...]
        sa.Column("model_used", sa.String(50), nullable=False, server_default="gpt-4o"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_ai_photo_tags_org_id", "ai_photo_tags", ["org_id"])
    op.create_index("ix_ai_photo_tags_product_id", "ai_photo_tags", ["product_id"])

    op.create_table(
        "ai_price_suggestions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True),
                  sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("cost_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("target_margin_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("current_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("suggested_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("model_used", sa.String(50), nullable=False, server_default="gpt-4o"),
        sa.Column("accepted", sa.Boolean(), nullable=True),
        sa.Column("accepted_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_ai_price_suggestions_org_id", "ai_price_suggestions", ["org_id"])
    op.create_index("ix_ai_price_suggestions_product_id",
                    "ai_price_suggestions", ["product_id"])

    op.create_table(
        "ai_customer_personas",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("behavior_traits", JSONB(), nullable=False, server_default="'[]'"),
        # [{trait: "high_value", score: 0.9}, ...]
        sa.Column("customer_ids", JSONB(), nullable=False, server_default="'[]'"),
        # list of customer UUID strings in this cluster
        sa.Column("segment_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_ai_customer_personas_org_id", "ai_customer_personas", ["org_id"])


def downgrade() -> None:
    op.drop_table("ai_customer_personas")
    op.drop_table("ai_price_suggestions")
    op.drop_table("ai_photo_tags")
    op.drop_table("ai_email_drafts")
    op.drop_table("ai_product_descriptions")
    op.drop_table("anomaly_notifications")
    op.drop_table("voice_report_queries")
    op.drop_table("push_notification_tokens")
    op.drop_table("mobile_kpi_configs")
    op.drop_table("statement_requests")
