"""v21: portal session registry — replay prevention for portal JWTs

Revision ID: a1c3e5f7b9d4
Revises: f0a2c4e6d8b1
Create Date: 2026-04-22

Adds ``portal_sessions`` so every issued portal JWT is tracked by its
``jti`` claim. On every authenticated portal request we look up the
session row; if it is missing, expired, or revoked the request is
rejected. This closes two replay gaps:

  1. A stolen portal JWT can be revoked mid-lifetime (logout, or when
     the customer requests a fresh magic link).
  2. A token that was never issued by us but happens to share our
     PORTAL_JWT_SECRET (compromised secret, dev token replayed to prod)
     cannot forge access because its jti will not exist in the table.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a1c3e5f7b9d4"
down_revision = "f0a2c4e6d8b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portal_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # jti is the JWT ID claim we embed in every portal JWT. Unique
        # because two JWTs must never share a jti — otherwise revoking
        # one would revoke the other.
        sa.Column("jti", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_portal_sessions_expires_at", "portal_sessions", ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_portal_sessions_expires_at", table_name="portal_sessions")
    op.drop_table("portal_sessions")
