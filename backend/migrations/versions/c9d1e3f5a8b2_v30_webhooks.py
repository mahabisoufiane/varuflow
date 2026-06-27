"""v30: outbound webhooks + ENTERPRISE plan tier

Revision ID: c9d1e3f5a8b2
Revises: b8c0d2e4f6a7
Create Date: 2026-04-23

Adds:
- ``ENTERPRISE`` value to the existing ``org_plan`` Postgres enum so the
  webhooks endpoints can be plan-gated above PRO.
- ``webhook_endpoints``: per-org outbound HTTP destinations with an
  HMAC secret hash and an array of subscribed event types.
- ``webhook_deliveries``: append-only log of every dispatch attempt with
  status code, retry counter and the next exponential-backoff timestamp
  the scheduler should re-attempt at.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c9d1e3f5a8b2"
down_revision = "b8c0d2e4f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block on
    # older PG versions; opening an autocommit connection keeps this
    # migration portable. The IF NOT EXISTS guard makes it idempotent
    # so re-running locally doesn't blow up.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE org_plan ADD VALUE IF NOT EXISTS 'ENTERPRISE'")

    op.create_table(
        "webhook_endpoints",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.String(length=2048), nullable=False),
        # SHA-256 hash of the secret. The plaintext is shown ONCE on
        # registration and never persisted — same model as a Stripe
        # webhook signing secret.
        sa.Column("secret_hash", sa.String(length=128), nullable=False),
        sa.Column(
            "events",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_webhook_endpoints_org_id",
        "webhook_endpoints",
        ["org_id"],
    )

    op.create_table(
        "webhook_deliveries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "endpoint_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_webhook_deliveries_endpoint_id",
        "webhook_deliveries",
        ["endpoint_id"],
    )
    # Partial index — the retry sweep scans only rows that still need
    # work, which keeps the query fast even after years of history.
    op.create_index(
        "ix_webhook_deliveries_pending_retry",
        "webhook_deliveries",
        ["next_retry_at"],
        postgresql_where=sa.text("delivered_at IS NULL AND next_retry_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_webhook_deliveries_pending_retry", table_name="webhook_deliveries",
    )
    op.drop_index(
        "ix_webhook_deliveries_endpoint_id", table_name="webhook_deliveries",
    )
    op.drop_table("webhook_deliveries")
    op.drop_index(
        "ix_webhook_endpoints_org_id", table_name="webhook_endpoints",
    )
    op.drop_table("webhook_endpoints")
    # Postgres has no ALTER TYPE ... DROP VALUE — leave the enum value
    # in place. Existing rows with plan='ENTERPRISE' would block the
    # drop anyway and rolling back this migration after sales has
    # signed an Enterprise customer would be wrong.
