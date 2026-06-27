"""crm3 — email_sequences, email_sequence_steps, email_sequence_enrollments

Revision ID: j9e0f1g2h3i4
Revises:     i8d9e0f1g2h3
Create Date: 2026-04-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "j9e0f1g2h3i4"
down_revision = "i8d9e0f1g2h3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_sequences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("trigger_type", sa.String(30), nullable=True),
        sa.Column("trigger_value", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_id", "name", name="uq_email_sequences_org_name"),
    )
    op.create_index("ix_email_sequences_org_id", "email_sequences", ["org_id"])

    op.create_table(
        "email_sequence_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sequence_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("email_sequences.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_number", sa.Integer, nullable=False),
        sa.Column("delay_days", sa.Integer, nullable=False, server_default="0"),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("body_html", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("sequence_id", "step_number", name="uq_seq_step_number"),
    )
    op.create_index("ix_email_sequence_steps_sequence_id", "email_sequence_steps", ["sequence_id"])

    op.create_table(
        "email_sequence_enrollments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sequence_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("email_sequences.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("current_step", sa.Integer, nullable=False, server_default="0"),
        sa.Column("next_send_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("sequence_id", "customer_id", name="uq_seq_enrollment_customer"),
    )
    op.create_index("ix_email_sequence_enrollments_org_id", "email_sequence_enrollments", ["org_id"])
    op.create_index("ix_email_sequence_enrollments_next_send_at", "email_sequence_enrollments", ["next_send_at"])


def downgrade() -> None:
    op.drop_table("email_sequence_enrollments")
    op.drop_table("email_sequence_steps")
    op.drop_table("email_sequences")
