"""v44: session_version for JWT invalidation on password change (Item 24).

Adds ``auth_users.session_version INT NOT NULL DEFAULT 1``.

When the server mints an access token it embeds the current
``session_version`` as a ``ver`` claim. On every request the auth
middleware compares the token's claim to the DB column — a password
reset (or any other "kick every session" event) bumps the column,
immediately retiring every outstanding JWT for that user without
waiting for the access-token TTL to elapse.

Additive migration; ``NOT NULL DEFAULT 1`` means all existing rows
backfill in one DDL without an explicit UPDATE. Old tokens minted
before this deploy carry no ``ver`` claim — the middleware treats a
missing claim as legacy-pass (documented compromise in the router
code) so the rollout doesn't log every active user out. Sessions
created after this deploy get full enforcement.
"""
from alembic import op
import sqlalchemy as sa


revision = "b5c7d9e1f3a5"
down_revision = "a4b6c8d0e2f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "auth_users",
        sa.Column(
            "session_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("auth_users", "session_version")
