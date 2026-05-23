"""v17: add created_at to stripe_processed_events for retention cleanup

Revision ID: c5d7e9f1a3b6
Revises: b4c6d8e0f2a5
Create Date: 2026-04-22

The idempotency table grows forever — every Stripe webhook ever received
leaves a row. Stripe's replay window is ≤30 days, so rows older than that
cannot possibly collide with a future retry. Add a ``created_at`` column
so the token_cleanup scheduler can prune stale entries.

Existing rows get ``created_at = NOW()`` at migration time; they will age
out within 30 days of deployment.
"""
from alembic import op
import sqlalchemy as sa

revision = "c5d7e9f1a3b6"
down_revision = "b4c6d8e0f2a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stripe_processed_events",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )


def downgrade() -> None:
    op.drop_column("stripe_processed_events", "created_at")
