"""v67 — Self-service booking check-in tokens (Item 58).

One row per generated check-in link. The token itself is never
stored — only its SHA-256 hash — so a leaked DB backup can't be
replayed to check anyone in. Tokens are single-use (``used_at``
timestamp) and time-limited.

Shape is deliberately small: ``appointment_id`` + ``token_hash`` are
enough for the check-in endpoint to locate the row, verify it and
stamp ``used_at``. A separate ``checked_in_at`` column on
``appointments`` records the customer-facing check-in event and is
what the booking UI reads.

Revision: c7e9a1b3d5f8
Revises:  b6d8f0a2c4e7 (v66 — staff availability, Item 57)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c7e9a1b3d5f8"
down_revision = "b6d8f0a2c4e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "appointment_checkin_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "appointment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("appointments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_checkin_tokens_appointment",
        "appointment_checkin_tokens",
        ["appointment_id"],
    )
    op.create_index(
        "ix_checkin_tokens_org_expires",
        "appointment_checkin_tokens",
        ["org_id", "expires_at"],
    )
    # Customer-facing check-in timestamp on the appointment itself.
    op.add_column(
        "appointments",
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("appointments", "checked_in_at")
    op.drop_index(
        "ix_checkin_tokens_org_expires", table_name="appointment_checkin_tokens"
    )
    op.drop_index(
        "ix_checkin_tokens_appointment", table_name="appointment_checkin_tokens"
    )
    op.drop_table("appointment_checkin_tokens")
