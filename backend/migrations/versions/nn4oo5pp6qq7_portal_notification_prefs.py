"""Portal notification preferences.

Revision ID: nn4oo5pp6qq7
Revises: mm3nn4oo5pp6
Create Date: 2026-05-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "nn4oo5pp6qq7"
down_revision = "mm3nn4oo5pp6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portal_notification_preferences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True),
                  sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_created", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("payment_received", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("quote_sent", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("appointment_reminder", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("marketing", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("customer_id", name="uq_portal_notif_prefs_customer"),
    )
    op.create_index("ix_portal_notif_prefs_org_id", "portal_notification_preferences", ["org_id"])


def downgrade() -> None:
    op.drop_table("portal_notification_preferences")
