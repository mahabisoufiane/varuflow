"""v13: idempotency_keys table for client-supplied Idempotency-Key header

Revision ID: e1f3a5b7c9d2
Revises: d7f9b2c4e5a8
Create Date: 2026-04-22

Caller-supplied idempotency for write endpoints (initially POST /invoices):
a request carrying an Idempotency-Key header is resolved to the same resource
on retry, preventing double-creation from flaky networks or Stripe webhook
redelivery-style clients.

Keys are scoped per (org_id, endpoint) so two orgs can reuse identical keys
and the same key can safely appear in distinct endpoints.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e1f3a5b7c9d2"
down_revision = "d7f9b2c4e5a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.String(64), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("target_id", sa.String(128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("org_id", "endpoint", "key", name="uq_idempotency_keys_scope"),
    )
    op.create_index("ix_idempotency_keys_org_id", "idempotency_keys", ["org_id"])
    op.create_index("ix_idempotency_keys_created_at", "idempotency_keys", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_idempotency_keys_created_at", table_name="idempotency_keys")
    op.drop_index("ix_idempotency_keys_org_id", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
