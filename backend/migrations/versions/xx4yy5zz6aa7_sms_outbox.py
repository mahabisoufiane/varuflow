"""sms_outbox — SMS/WhatsApp outbox with opt-out and delivery tracking

Revision ID: xx4yy5zz6aa7
Revises: ww3xx4yy5zz6
Create Date: 2026-05-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "xx4yy5zz6aa7"
down_revision = "ww3xx4yy5zz6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sms_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("to_number", sa.String(30), nullable=False),
        sa.Column("from_number", sa.String(30), nullable=True),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("channel", sa.String(10), nullable=False, server_default="sms"),  # sms | whatsapp
        sa.Column("direction", sa.String(4), nullable=False, server_default="out"),  # out | in
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        # status: queued | sent | delivered | failed | undelivered | read
        sa.Column("provider_sid", sa.String(100), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cost_credits", sa.Numeric(8, 4), nullable=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ref_type", sa.String(50), nullable=True),
        sa.Column("ref_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sms_messages_org_id", "sms_messages", ["org_id"])
    op.create_index("ix_sms_messages_customer_id", "sms_messages", ["customer_id"])
    op.create_index("ix_sms_messages_to_number", "sms_messages", ["to_number"])

    op.create_table(
        "sms_opt_outs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phone_number", sa.String(30), nullable=False),
        sa.Column("channel", sa.String(10), nullable=False, server_default="sms"),
        sa.Column("opted_out_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_id", "phone_number", "channel", name="uq_sms_opt_out"),
    )
    op.create_index("ix_sms_opt_outs_org_phone", "sms_opt_outs", ["org_id", "phone_number"])


def downgrade() -> None:
    op.drop_table("sms_opt_outs")
    op.drop_table("sms_messages")
