"""v10: stripe_processed_events table for webhook idempotency

Revision ID: b4d6f0a2c8e1
Revises: a9b1c3d5e7f2
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "b4d6f0a2c8e1"
down_revision = "a9b1c3d5e7f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stripe_processed_events",
        sa.Column("id",       UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", sa.String(100),     nullable=False),
    )
    op.create_index(
        "ix_stripe_processed_events_event_id",
        "stripe_processed_events",
        ["event_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_stripe_processed_events_event_id", table_name="stripe_processed_events")
    op.drop_table("stripe_processed_events")
