"""v8 — standalone local auth tables

Revision ID: b3c5e9f1a2d4
Revises: a1b2c3d4e5f6
Create Date: 2026-04-11 00:00:00.000000

Tables added:
  auth_users           — local user accounts with bcrypt, TOTP, lockout
  auth_refresh_tokens  — hashed refresh tokens (SHA-256)
  auth_login_attempts  — audit log for every login attempt
"""
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b3c5e9f1a2d4"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── auth_users ─────────────────────────────────────────────────────────────
    op.create_table(
        "auth_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(72), nullable=False),
        # Email verification
        sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("email_verification_token", sa.String(64), nullable=True),
        sa.Column("email_verification_sent_at", sa.DateTime(timezone=True), nullable=True),
        # TOTP
        sa.Column("totp_secret", sa.String(64), nullable=True),
        sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("totp_provisioning_uri", sa.Text(), nullable=True),
        # Lockout
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        # Password reset
        sa.Column("password_reset_token", sa.String(64), nullable=True),
        sa.Column("password_reset_expires_at", sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_auth_users_email", "auth_users", ["email"], unique=True)
    op.create_index(
        "ix_auth_users_email_verification_token",
        "auth_users",
        ["email_verification_token"],
    )
    op.create_index(
        "ix_auth_users_password_reset_token",
        "auth_users",
        ["password_reset_token"],
    )

    # ── auth_refresh_tokens ────────────────────────────────────────────────────
    op.create_table(
        "auth_refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("auth_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_auth_refresh_tokens_token_hash", "auth_refresh_tokens", ["token_hash"], unique=True
    )
    op.create_index(
        "ix_auth_refresh_tokens_user_id", "auth_refresh_tokens", ["user_id"]
    )
    op.create_index(
        "ix_auth_refresh_tokens_user_id_revoked",
        "auth_refresh_tokens",
        ["user_id", "revoked"],
    )

    # ── auth_login_attempts ────────────────────────────────────────────────────
    op.create_table(
        "auth_login_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("auth_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=False),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("failure_reason", sa.String(128), nullable=True),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_auth_login_attempts_email", "auth_login_attempts", ["email"])
    op.create_index("ix_auth_login_attempts_user_id", "auth_login_attempts", ["user_id"])
    op.create_index(
        "ix_auth_login_attempts_attempted_at", "auth_login_attempts", ["attempted_at"]
    )


def downgrade() -> None:
    op.drop_table("auth_login_attempts")
    op.drop_table("auth_refresh_tokens")
    op.drop_table("auth_users")
