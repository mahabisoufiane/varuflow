"""v105 — trial onboarding email sequence tables

Revision ID: d4e5f6g7h8i9
Revises: c3n4p5s6u7v8
Create Date: 2026-05-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d4e5f6g7h8i9"
down_revision = "c3n4p5s6u7v8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── trial_sequences ───────────────────────────────────────────────────────
    op.create_table(
        "trial_sequences",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("trigger_event", sa.String(100), nullable=False),
        sa.Column("locale", sa.String(10), nullable=False, server_default="en"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.UniqueConstraint("name", "locale", name="uq_trial_sequences_name_locale"),
    )

    # ── trial_sequence_steps ──────────────────────────────────────────────────
    op.create_table(
        "trial_sequence_steps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "sequence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trial_sequences.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("delay_days", sa.Integer(), nullable=False),
        sa.Column("email_template_key", sa.String(100), nullable=False),
        sa.Column(
            "send_only_if",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "sequence_id", "step_number", name="uq_trial_sequence_steps_seq_step"
        ),
    )
    op.create_index(
        "ix_trial_sequence_steps_sequence_id",
        "trial_sequence_steps",
        ["sequence_id"],
    )

    # ── trial_enrollments ─────────────────────────────────────────────────────
    op.create_table(
        "trial_enrollments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "sequence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trial_sequences.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_send_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_reason", sa.String(50), nullable=True),
        sa.Column("locale", sa.String(10), nullable=False, server_default="en"),
        sa.UniqueConstraint(
            "sequence_id", "org_id", name="uq_trial_enrollments_seq_org"
        ),
    )
    op.create_index(
        "ix_trial_enrollments_org_id",
        "trial_enrollments",
        ["org_id"],
    )
    op.create_index(
        "ix_trial_enrollments_next_send_completed",
        "trial_enrollments",
        ["next_send_at", "completed_at"],
    )

    # ── trial_email_sends ─────────────────────────────────────────────────────
    op.create_table(
        "trial_email_sends",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "enrollment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trial_enrollments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("email_template_key", sa.String(100), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("to_email", sa.String(255), nullable=False),
        sa.Column("resend_message_id", sa.String(200), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bounced_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "enrollment_id", "step_number", name="uq_trial_email_sends_enrollment_step"
        ),
    )
    op.create_index(
        "ix_trial_email_sends_enrollment_id",
        "trial_email_sends",
        ["enrollment_id"],
    )


def downgrade() -> None:
    op.drop_table("trial_email_sends")
    op.drop_table("trial_enrollments")
    op.drop_table("trial_sequence_steps")
    op.drop_table("trial_sequences")
