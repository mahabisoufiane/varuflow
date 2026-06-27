"""v59 — API developer keys (Item 45).

Two new tables:

* ``api_keys`` — one row per ENTERPRISE-issued key. Stores the
  SHA-256 hash of the secret only; the plaintext is shown to the
  user exactly once at creation time.
* ``api_key_usages`` — append-only log of recent calls per key.
  Bounded to ~100 rows per key by the router (oldest rows
  pruned on insert).

Spec suggested v51; v51 already taken by ``c9d0e1f2a3b4_v51_loyalty.py``.
Following the same convention used in §69-§73 we land at the next
free slot — v59 (chains from v58 documents).

Revision: a8b1c3d5e7f2
Revises:  e4f6a8b1c3d5 (v58 — documents, Item 44)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a8b1c3d5e7f2"
down_revision = "e4f6a8b1c3d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        # Public prefix: first 8 chars of the secret, shown in the UI
        # so the operator can identify a key without seeing its full
        # value. Indexed because it's also the lookup column for
        # incoming requests (paired with the hash for verification).
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        # SHA-256 hex digest of the full secret. Plaintext is shown
        # once on issue and never persisted.
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        # Scopes as JSONB so we can extend without migrations. The
        # service-layer allow-list keeps it honest — DB is permissive.
        sa.Column(
            "scopes",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True), nullable=True,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "is_revoked",
            sa.Boolean, nullable=False, server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Tenant scope index.
    op.create_index("ix_api_keys_org", "api_keys", ["org_id"])
    # Lookup at request time: prefix is short and unique-enough to
    # narrow the candidate set to one row in practice. The unique
    # constraint also defends against a (vanishingly unlikely) prefix
    # collision turning into a silent verification mismatch.
    op.create_index(
        "ix_api_keys_prefix",
        "api_keys",
        ["key_prefix"],
        unique=True,
    )
    # Active-keys lookup — partial index keeps the hot scan tiny.
    op.create_index(
        "ix_api_keys_active",
        "api_keys",
        ["org_id"],
        postgresql_where=sa.text("is_revoked = false"),
    )

    op.create_table(
        "api_key_usages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "key_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("api_keys.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "called_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("status_code", sa.Integer, nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
    )
    # The "show me last 100 calls for this key" lookup. Composite on
    # (key_id, called_at desc) so the trim-on-insert pruning is a
    # single index scan.
    op.create_index(
        "ix_api_key_usages_key_called",
        "api_key_usages",
        ["key_id", "called_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_api_key_usages_key_called", table_name="api_key_usages")
    op.drop_table("api_key_usages")
    op.drop_index("ix_api_keys_active", table_name="api_keys")
    op.drop_index("ix_api_keys_prefix", table_name="api_keys")
    op.drop_index("ix_api_keys_org", table_name="api_keys")
    op.drop_table("api_keys")
