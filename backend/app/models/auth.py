"""SQLAlchemy models for the standalone auth system.

Tables:
  auth_users           — local user accounts (separate from Supabase)
  auth_refresh_tokens  — hashed refresh tokens, one active per user
  auth_login_attempts  — audit log for every login attempt
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base
from app.services.encryption import EncryptedString


class AuthUser(Base):
    __tablename__ = "auth_users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(72), nullable=False)

    # Email verification
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verification_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    email_verification_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # TOTP / MFA — Item 28: encrypted at rest via EncryptedString.
    # Column widened from String(64) to 512 in migration v46 to fit the
    # Fernet ciphertext (~140 chars for a 32-char Base32 secret + the
    # ``penc:v1:`` prefix + rotation headroom). Legacy plaintext rows
    # written pre-v46 still decrypt transparently.
    totp_secret: Mapped[str | None] = mapped_column(EncryptedString(512), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    totp_provisioning_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set to ``now()`` when the user confirms TOTP on an org that requires
    # MFA (Item 23 / migration v43). Cleared on disable. Nullable so
    # users who enabled TOTP before enforcement shipped don't get a
    # fabricated timestamp — we only record enforcement activations we
    # actually observe.
    totp_enforced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Account lockout
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Session invalidation (Item 24 / migration v44). Bumped whenever every
    # outstanding access token for this user must be retired — password
    # reset, TOTP disable, or future "log out everywhere" events. The
    # minted JWT embeds the current value as a ``ver`` claim; the auth
    # middleware rejects any token whose claim is lower than the column.
    # Default 1 on backfill so existing rows start at parity with newly
    # minted tokens.
    session_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Password reset
    password_reset_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # BankID — SHA-256 of the 12-digit Swedish personnummer ("YYYYMMDDNNNN").
    # Raw personnummer is never persisted: it's PII under GDPR and
    # Folkbokföringslagen, and the hash is sufficient to look up an
    # existing account on login. Unique index is created at the DB level
    # by migration v24 so two accounts can never collide on the same
    # person.
    personalnummer_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    refresh_tokens: Mapped[list["AuthRefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    login_attempts: Mapped[list["AuthLoginAttempt"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class AuthRefreshToken(Base):
    __tablename__ = "auth_refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Store only the SHA-256 hash of the token — never the raw value
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6 max = 45 chars
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["AuthUser"] = relationship(back_populates="refresh_tokens")

    __table_args__ = (
        Index("ix_auth_refresh_tokens_user_id_revoked", "user_id", "revoked"),
    )


class AuthLoginAttempt(Base):
    __tablename__ = "auth_login_attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    user: Mapped[AuthUser | None] = relationship(back_populates="login_attempts")
