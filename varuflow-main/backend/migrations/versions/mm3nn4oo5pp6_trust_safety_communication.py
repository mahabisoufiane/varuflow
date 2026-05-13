"""Trust & Safety + Communication Layer.

Revision ID: mm3nn4oo5pp6
Revises:     ll2mm3nn4oo5
Create Date: 2026-05-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "mm3nn4oo5pp6"
down_revision = "ll2mm3nn4oo5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Trust & Safety ───────────────────────────────────────────────────────────

    op.create_table(
        "identity_verifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("booking_id", UUID(as_uuid=True),
                  sa.ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(30), nullable=False, server_default="manual"),
        # manual / stripe_identity / jumio / onfido
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        # pending / submitted / approved / rejected
        sa.Column("document_type", sa.String(30), nullable=True),
        sa.Column("document_ref", sa.String(200), nullable=True),
        # encrypted external reference
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_identity_verifications_org_id", "identity_verifications", ["org_id"])
    op.create_index("ix_identity_verifications_customer_id",
                    "identity_verifications", ["customer_id"])
    op.create_index("ix_identity_verifications_booking_id",
                    "identity_verifications", ["booking_id"])

    op.create_table(
        "staff_background_checks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_id", UUID(as_uuid=True),
                  sa.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("check_type", sa.String(30), nullable=False, server_default="dbs"),
        # dbs / dbs_enhanced / criminal / custom
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        # pending / clear / flagged / expired
        sa.Column("issued_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("badge_visible", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("reference_number", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_staff_background_checks_org_id", "staff_background_checks", ["org_id"])
    op.create_index("ix_staff_background_checks_staff_id",
                    "staff_background_checks", ["staff_id"])

    op.create_table(
        "service_insurance_addons",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_id", UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("coverage_description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_service_insurance_addons_org_id",
                    "service_insurance_addons", ["org_id"])

    op.create_table(
        "booking_insurance_purchases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("booking_id", UUID(as_uuid=True),
                  sa.ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("addon_id", UUID(as_uuid=True),
                  sa.ForeignKey("service_insurance_addons.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("amount_paid", sa.Numeric(10, 2), nullable=False),
        sa.Column("policy_ref", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        # active / claimed / expired / refunded
        sa.Column("expires_at", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_booking_insurance_purchases_org_id",
                    "booking_insurance_purchases", ["org_id"])
    op.create_index("ix_booking_insurance_purchases_customer_id",
                    "booking_insurance_purchases", ["customer_id"])

    op.create_table(
        "disputes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("booking_id", UUID(as_uuid=True),
                  sa.ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("invoice_id", UUID(as_uuid=True),
                  sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("type", sa.String(30), nullable=False, server_default="other"),
        # service_quality / no_show / damage / billing / other
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        # open / in_review / resolved / escalated / closed
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("opened_by", sa.String(10), nullable=False, server_default="customer"),
        # customer / merchant
        sa.Column("resolved_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_disputes_org_id", "disputes", ["org_id"])
    op.create_index("ix_disputes_customer_id", "disputes", ["customer_id"])
    op.create_index("ix_disputes_status", "disputes", ["org_id", "status"])

    op.create_table(
        "dispute_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("dispute_id", UUID(as_uuid=True),
                  sa.ForeignKey("disputes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_type", sa.String(10), nullable=False),
        # customer / staff / admin
        sa.Column("sender_name", sa.String(100), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("attachments", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_dispute_messages_dispute_id", "dispute_messages", ["dispute_id"])

    op.create_table(
        "merchant_customer_reviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("booking_id", UUID(as_uuid=True),
                  sa.ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        # 1–5
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("tags", JSONB(), nullable=False, server_default="'[]'"),
        # ["no_show", "late_payer", "great_client", …]
        sa.Column("is_private", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("shared_with_network", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_merchant_customer_reviews_org_id",
                    "merchant_customer_reviews", ["org_id"])
    op.create_index("ix_merchant_customer_reviews_customer_id",
                    "merchant_customer_reviews", ["customer_id"])

    # ── Communication Layer ──────────────────────────────────────────────────────

    op.create_table(
        "unified_inbox_threads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=True),
        sa.Column("channel", sa.String(20), nullable=False, server_default="in_app"),
        # email / whatsapp / sms / in_app / contact_form / chat
        sa.Column("subject", sa.String(300), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("assigned_to_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("sentiment", sa.String(10), nullable=True),
        # positive / neutral / negative
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_unified_inbox_threads_org_id", "unified_inbox_threads", ["org_id"])
    op.create_index("ix_unified_inbox_threads_customer_id",
                    "unified_inbox_threads", ["customer_id"])
    op.create_index("ix_unified_inbox_threads_channel",
                    "unified_inbox_threads", ["org_id", "channel"])
    op.create_index("ix_unified_inbox_threads_last_message",
                    "unified_inbox_threads", ["org_id", "last_message_at"])

    op.create_table(
        "unified_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("thread_id", UUID(as_uuid=True),
                  sa.ForeignKey("unified_inbox_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=True),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False, server_default="inbound"),
        # inbound / outbound
        sa.Column("external_message_id", sa.String(200), nullable=True),
        sa.Column("sender_name", sa.String(200), nullable=True),
        sa.Column("sender_contact", sa.String(200), nullable=True),
        sa.Column("subject", sa.String(300), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("assigned_to_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("parent_message_id", UUID(as_uuid=True), nullable=True),
        # no FK constraint to avoid circular reference complexity
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_unified_messages_org_id", "unified_messages", ["org_id"])
    op.create_index("ix_unified_messages_thread_id", "unified_messages", ["thread_id"])
    op.create_index("ix_unified_messages_customer_id", "unified_messages", ["customer_id"])
    op.create_index("ix_unified_messages_channel_direction",
                    "unified_messages", ["org_id", "channel", "direction"])
    op.create_index("ix_unified_messages_is_read", "unified_messages", ["org_id", "is_read"])

    op.create_table(
        "message_translations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", UUID(as_uuid=True),
                  sa.ForeignKey("unified_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_language", sa.String(5), nullable=False),
        sa.Column("target_language", sa.String(5), nullable=False),
        sa.Column("translated_body", sa.Text(), nullable=False),
        sa.Column("translated_by", sa.String(20), nullable=False, server_default="openai"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("message_id", "target_language",
                            name="uq_message_translations_msg_lang"),
    )
    op.create_index("ix_message_translations_org_id", "message_translations", ["org_id"])
    op.create_index("ix_message_translations_message_id",
                    "message_translations", ["message_id"])

    op.create_table(
        "smart_reply_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", UUID(as_uuid=True),
                  sa.ForeignKey("unified_messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("suggestions", JSONB(), nullable=False, server_default="'[]'"),
        # [{text: str, tone: str}] × 3
        sa.Column("accepted_index", sa.Integer(), nullable=True),
        # which suggestion was used (0/1/2), null if none
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_smart_reply_logs_org_id", "smart_reply_logs", ["org_id"])
    op.create_index("ix_smart_reply_logs_message_id", "smart_reply_logs", ["message_id"])

    op.create_table(
        "conversation_sentiment_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("thread_id", UUID(as_uuid=True),
                  sa.ForeignKey("unified_inbox_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", UUID(as_uuid=True),
                  sa.ForeignKey("unified_messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sentiment", sa.String(10), nullable=False),
        # positive / neutral / negative
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("flagged_for_manager", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_conversation_sentiment_logs_org_id",
                    "conversation_sentiment_logs", ["org_id"])
    op.create_index("ix_conversation_sentiment_logs_thread_id",
                    "conversation_sentiment_logs", ["thread_id"])
    op.create_index("ix_conversation_sentiment_logs_flagged",
                    "conversation_sentiment_logs", ["org_id", "flagged_for_manager"])


def downgrade() -> None:
    op.drop_table("conversation_sentiment_logs")
    op.drop_table("smart_reply_logs")
    op.drop_table("message_translations")
    op.drop_table("unified_messages")
    op.drop_table("unified_inbox_threads")
    op.drop_table("merchant_customer_reviews")
    op.drop_table("dispute_messages")
    op.drop_table("disputes")
    op.drop_table("booking_insurance_purchases")
    op.drop_table("service_insurance_addons")
    op.drop_table("staff_background_checks")
    op.drop_table("identity_verifications")
