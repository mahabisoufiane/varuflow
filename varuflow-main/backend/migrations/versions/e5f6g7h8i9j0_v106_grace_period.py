"""v106 — subscription grace period table

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-05-02
"""
from alembic import op
import sqlalchemy as sa

revision = "e5f6g7h8i9j0"
down_revision = "d4e5f6g7h8i9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    grace_status = sa.Enum("active", "recovered", "expired", name="grace_period_status")
    grace_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "subscription_grace_periods",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failed_invoice_id", sa.String(255)),
        sa.Column("failed_amount_cents", sa.Integer()),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("status", grace_status, nullable=False, server_default="active"),
        sa.Column("recovered_at", sa.DateTime(timezone=True)),
        sa.Column("expired_at", sa.DateTime(timezone=True)),
        sa.Column("notification_sent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_notification_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("subscription_grace_periods")
    sa.Enum(name="grace_period_status").drop(op.get_bind(), checkfirst=True)
