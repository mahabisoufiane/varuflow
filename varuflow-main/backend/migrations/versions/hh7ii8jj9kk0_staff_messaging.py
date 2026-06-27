"""Internal staff messaging

Revision ID: hh7ii8jj9kk0
Revises: gg6hh7ii8jj9
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "hh7ii8jj9kk0"
down_revision = "gg6hh7ii8jj9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Direct messages between staff members.
    # NULL recipient_id means the message was sent to a named channel
    # (channel column stores the channel slug, e.g. "general").
    # Either recipient_id OR channel must be non-NULL — enforced at
    # application level; the DB allows both NULL for draft support.
    op.create_table(
        "staff_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("sender_id", UUID(as_uuid=True),
                  nullable=True),
        sa.Column("recipient_id", UUID(as_uuid=True),
                  nullable=True),
        # channel slug for group/broadcast messages, e.g. "general", "ops"
        sa.Column("channel", sa.String(50), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        # For DMs: set when the recipient first fetches the conversation.
        # For channel messages: ignored (use staff_message_reads instead).
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_staff_messages_org_recipient",
                    "staff_messages", ["org_id", "recipient_id"])
    op.create_index("ix_staff_messages_org_sender",
                    "staff_messages", ["org_id", "sender_id"])
    op.create_index("ix_staff_messages_org_channel",
                    "staff_messages", ["org_id", "channel"])
    op.create_index("ix_staff_messages_created",
                    "staff_messages", ["org_id", "created_at"])

    # Per-staff read receipts for channel messages.
    # One row per (staff_member, message) once they've seen it.
    op.create_table(
        "staff_message_reads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("message_id", UUID(as_uuid=True),
                  sa.ForeignKey("staff_messages.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("staff_id", UUID(as_uuid=True),
                  nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_staff_message_reads_msg_staff",
                    "staff_message_reads", ["message_id", "staff_id"],
                    unique=True)
    op.create_index("ix_staff_message_reads_staff",
                    "staff_message_reads", ["staff_id"])


def downgrade() -> None:
    op.drop_table("staff_message_reads")
    op.drop_table("staff_messages")
