"""Trust & Verification + Customer Service Layer.

Revision ID: ll2mm3nn4oo5
Revises:     kk1ll2mm3nn4
Create Date: 2026-05-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "ll2mm3nn4oo5"
down_revision = "kk1ll2mm3nn4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Trust & Verification ─────────────────────────────────────────────────────

    op.create_table(
        "service_reviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("booking_id", UUID(as_uuid=True),
                  sa.ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("product_id", UUID(as_uuid=True), nullable=True),
        sa.Column("service_id", UUID(as_uuid=True), nullable=True),
        sa.Column("staff_id", UUID(as_uuid=True), nullable=True),
        sa.Column("reviewer_name", sa.String(100), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        # 1–5 stars
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("is_verified_purchase", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("reply_text", sa.Text(), nullable=True),
        sa.Column("replied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_service_reviews_org_id", "service_reviews", ["org_id"])
    op.create_index("ix_service_reviews_customer_id", "service_reviews", ["customer_id"])
    op.create_index("ix_service_reviews_booking_id", "service_reviews", ["booking_id"])
    op.create_index("ix_service_reviews_rating", "service_reviews", ["org_id", "rating"])

    op.create_table(
        "staff_credentials",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_id", UUID(as_uuid=True),
                  sa.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False),
        sa.Column("credential_type", sa.String(30), nullable=False, server_default="certification"),
        # certification / training / award / experience / other
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("issuing_body", sa.String(200), nullable=True),
        sa.Column("issued_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("is_visible_to_customers", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_staff_credentials_org_id", "staff_credentials", ["org_id"])
    op.create_index("ix_staff_credentials_staff_id", "staff_credentials", ["staff_id"])

    op.create_table(
        "booking_slots_config",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_id", UUID(as_uuid=True), nullable=True),
        sa.Column("staff_id", UUID(as_uuid=True), nullable=True),
        sa.Column("period_type", sa.String(10), nullable=False, server_default="week"),
        # week / day
        sa.Column("total_slots", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("show_urgency_below", sa.Integer(), nullable=False, server_default="5"),
        # show "X slots left" message when remaining <= this number
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", "service_id", "staff_id", "period_type",
                            name="uq_booking_slots_config_org_service_staff_period"),
    )
    op.create_index("ix_booking_slots_config_org_id", "booking_slots_config", ["org_id"])

    op.create_table(
        "staff_portfolio_photos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_id", UUID(as_uuid=True),
                  sa.ForeignKey("staff.id", ondelete="CASCADE"), nullable=True),
        sa.Column("service_id", UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("photo_url", sa.String(500), nullable=False),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_staff_portfolio_photos_org_id", "staff_portfolio_photos", ["org_id"])
    op.create_index("ix_staff_portfolio_photos_staff_id",
                    "staff_portfolio_photos", ["staff_id"])

    # ── Customer Service Layer ───────────────────────────────────────────────────

    op.create_table(
        "live_chat_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("visitor_id", UUID(as_uuid=True), nullable=False),
        sa.Column("visitor_name", sa.String(100), nullable=True),
        sa.Column("visitor_email", sa.String(200), nullable=True),
        sa.Column("assigned_staff_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        # open / in_progress / resolved / abandoned
        sa.Column("page_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_live_chat_sessions_org_id", "live_chat_sessions", ["org_id"])
    op.create_index("ix_live_chat_sessions_visitor_id", "live_chat_sessions", ["visitor_id"])
    op.create_index("ix_live_chat_sessions_status", "live_chat_sessions", ["org_id", "status"])

    op.create_table(
        "live_chat_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True),
                  sa.ForeignKey("live_chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_type", sa.String(10), nullable=False),
        # visitor / staff / bot
        sa.Column("sender_name", sa.String(100), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_live_chat_messages_session_id", "live_chat_messages", ["session_id"])

    op.create_table(
        "chatbot_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("welcome_message", sa.Text(), nullable=True),
        sa.Column("escalation_threshold", sa.Integer(), nullable=False, server_default="3"),
        # escalate to human after N bot responses without resolution
        sa.Column("knowledge_base_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("handoff_email", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", name="uq_chatbot_configs_org"),
    )
    op.create_index("ix_chatbot_configs_org_id", "chatbot_configs", ["org_id"])

    op.create_table(
        "chatbot_conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("visitor_id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True),
                  sa.ForeignKey("live_chat_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("messages", JSONB(), nullable=False, server_default="'[]'"),
        # [{role: visitor|bot, content: str, ts: iso}]
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_chatbot_conversations_org_id", "chatbot_conversations", ["org_id"])
    op.create_index("ix_chatbot_conversations_visitor_id",
                    "chatbot_conversations", ["visitor_id"])

    op.create_table(
        "kb_categories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", "name", name="uq_kb_categories_org_name"),
    )
    op.create_index("ix_kb_categories_org_id", "kb_categories", ["org_id"])

    op.create_table(
        "kb_articles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", UUID(as_uuid=True),
                  sa.ForeignKey("kb_categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("slug", sa.String(300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        # markdown
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("helpful_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("not_helpful_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", "slug", name="uq_kb_articles_org_slug"),
    )
    op.create_index("ix_kb_articles_org_id", "kb_articles", ["org_id"])
    op.create_index("ix_kb_articles_category_id", "kb_articles", ["category_id"])

    op.create_table(
        "return_pickup_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", UUID(as_uuid=True),
                  sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("return_request_id", UUID(as_uuid=True), nullable=True),
        sa.Column("courier_provider", sa.String(50), nullable=True),
        sa.Column("pickup_address_line1", sa.String(200), nullable=False),
        sa.Column("pickup_address_city", sa.String(100), nullable=False),
        sa.Column("pickup_postal_code", sa.String(20), nullable=True),
        sa.Column("pickup_country", sa.String(2), nullable=False, server_default="SE"),
        sa.Column("preferred_date", sa.Date(), nullable=False),
        sa.Column("preferred_time_slot", sa.String(20), nullable=False, server_default="morning"),
        # morning / afternoon / evening
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        # pending / scheduled / collected / failed
        sa.Column("courier_tracking_number", sa.String(100), nullable=True),
        sa.Column("courier_booked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_return_pickup_requests_org_id", "return_pickup_requests", ["org_id"])
    op.create_index("ix_return_pickup_requests_customer_id",
                    "return_pickup_requests", ["customer_id"])


def downgrade() -> None:
    op.drop_table("return_pickup_requests")
    op.drop_table("kb_articles")
    op.drop_table("kb_categories")
    op.drop_table("chatbot_conversations")
    op.drop_table("chatbot_configs")
    op.drop_table("live_chat_messages")
    op.drop_table("live_chat_sessions")
    op.drop_table("staff_portfolio_photos")
    op.drop_table("booking_slots_config")
    op.drop_table("staff_credentials")
    op.drop_table("service_reviews")
