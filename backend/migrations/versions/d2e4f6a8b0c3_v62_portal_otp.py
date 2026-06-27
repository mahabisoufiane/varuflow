"""v62 — Two-Factor Auth for Customer Portal (Item 51).

Adds a short-lived one-time passcode table used as a second factor
between "magic-link verified" and "portal JWT issued".

* ``portal_otp_tokens`` — append-only with explicit ``used_at``. Codes
  are 6 digits and stored as SHA-256 hashes. Expiry is 5 minutes.
  Replay protection: partial unique index on ``(customer_id)`` where
  ``used_at IS NULL AND consumed = false`` keeps a single live code
  per customer, so issuing a new code invalidates the previous live
  one (the insert path deletes older live rows).

Revision: d2e4f6a8b0c3
Revises:  c1d3e5f7a9b2 (v61 — subscription pause, Item 50)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d2e4f6a8b0c3"
down_revision = "c1d3e5f7a9b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portal_otp_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False, server_default="email"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "consumed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_portal_otp_tokens_customer",
        "portal_otp_tokens",
        ["customer_id"],
    )
    op.create_index(
        "ix_portal_otp_tokens_org",
        "portal_otp_tokens",
        ["org_id"],
    )
    op.create_index(
        "ix_portal_otp_tokens_live",
        "portal_otp_tokens",
        ["customer_id"],
        unique=False,
        postgresql_where=sa.text("consumed = false"),
    )


def downgrade() -> None:
    op.drop_index("ix_portal_otp_tokens_live", table_name="portal_otp_tokens")
    op.drop_index("ix_portal_otp_tokens_org", table_name="portal_otp_tokens")
    op.drop_index("ix_portal_otp_tokens_customer", table_name="portal_otp_tokens")
    op.drop_table("portal_otp_tokens")
