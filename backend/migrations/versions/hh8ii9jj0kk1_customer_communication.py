"""Customer Communication — Two-Way Chat, Video Consultations, Voice Notes, Notification Prefs.

Revision ID: hh8ii9jj0kk1
Revises:     ff6gg7hh8ii9
Create Date: 2026-05-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "hh8ii9jj0kk1"
down_revision = "ff6gg7hh8ii9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── customer_chat_threads ────────────────────────────────────────────────────
    op.create_table(
        "customer_chat_threads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=True),
        sa.Column("subject", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        # open / resolved / closed
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unread_staff_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_customer_chat_threads_org_id", "customer_chat_threads", ["org_id"])
    op.create_index("ix_customer_chat_threads_customer_id",
                    "customer_chat_threads", ["customer_id"])
    op.create_index("ix_customer_chat_threads_last_msg",
                    "customer_chat_threads", ["last_message_at"])

    op.create_table(
        "customer_chat_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("thread_id", UUID(as_uuid=True),
                  sa.ForeignKey("customer_chat_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_type", sa.String(10), nullable=False),   # customer / staff
        sa.Column("sender_id", UUID(as_uuid=True), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("attachment_url", sa.Text(), nullable=True),
        sa.Column("attachment_type", sa.String(50), nullable=True),  # image/file/audio
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_customer_chat_messages_thread_id",
                    "customer_chat_messages", ["thread_id"])
    op.create_index("ix_customer_chat_messages_created_at",
                    "customer_chat_messages", ["created_at"])

    # ── video_consultations ──────────────────────────────────────────────────────
    op.create_table(
        "video_consultations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=True),
        sa.Column("appointment_id", UUID(as_uuid=True), nullable=True),
        sa.Column("staff_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(20), nullable=False, server_default="daily"),
        # daily / twilio
        sa.Column("room_name", sa.String(200), nullable=False),
        sa.Column("room_url", sa.Text(), nullable=True),
        sa.Column("staff_join_token", sa.Text(), nullable=True),
        sa.Column("customer_join_token", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        # scheduled / active / ended / cancelled
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("recording_url", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_video_consultations_org_id", "video_consultations", ["org_id"])
    op.create_index("ix_video_consultations_scheduled_for",
                    "video_consultations", ["scheduled_for"])

    # ── customer_voice_notes ─────────────────────────────────────────────────────
    op.create_table(
        "customer_voice_notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("thread_id", UUID(as_uuid=True),
                  sa.ForeignKey("customer_chat_threads.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sender_type", sa.String(10), nullable=False),   # customer / staff
        sa.Column("sender_id", UUID(as_uuid=True), nullable=True),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=True),
        sa.Column("appointment_id", UUID(as_uuid=True), nullable=True),
        sa.Column("audio_url", sa.Text(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("transcription", sa.Text(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_customer_voice_notes_org_id", "customer_voice_notes", ["org_id"])
    op.create_index("ix_customer_voice_notes_thread_id",
                    "customer_voice_notes", ["thread_id"])

    # ── customer_notification_prefs ──────────────────────────────────────────────
    op.create_table(
        "customer_notification_prefs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("remind_1_day", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("remind_1_hour", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("channel_push", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("channel_email", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("channel_sms", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", "customer_id",
                            name="uq_customer_notification_prefs_org_customer"),
    )
    op.create_index("ix_customer_notification_prefs_org_id",
                    "customer_notification_prefs", ["org_id"])
    op.create_index("ix_customer_notification_prefs_customer_id",
                    "customer_notification_prefs", ["customer_id"])


def downgrade() -> None:
    op.drop_table("customer_notification_prefs")
    op.drop_table("customer_voice_notes")
    op.drop_table("video_consultations")
    op.drop_table("customer_chat_messages")
    op.drop_table("customer_chat_threads")
