"""v46 — widen PII columns for encryption (Item 28)

Revision ID: d7e9f1a3b5c7
Revises: c6d8e0f2a4b6
Create Date: 2026-04-23 00:00:00

Item 28 introduces ``EncryptedString``, a SQLAlchemy ``TypeDecorator``
that wraps plaintext values in Fernet ciphertext before they hit the
DB. The ciphertext is ~100 bytes of Fernet overhead plus a 4/3 Base64
blow-up plus the ``penc:v1:`` prefix, which overflows the tight VARCHAR
limits the old plaintext columns were using. This migration widens the
affected columns; it does NOT encrypt any existing data. Legacy rows
stay plaintext and decrypt transparently via the module's fallback, so
the rollout is zero-downtime.

Backfill is optional and out of scope for this migration — see
docs/operations/security-hardening.md for the one-shot script.
"""
from alembic import op
import sqlalchemy as sa


revision = "d7e9f1a3b5c7"
down_revision = "c6d8e0f2a4b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # auth_users.totp_secret: 64 → 512
    op.alter_column(
        "auth_users", "totp_secret",
        existing_type=sa.String(length=64),
        type_=sa.String(length=512),
        existing_nullable=True,
    )
    # customers.email: 255 → 512
    op.alter_column(
        "customers", "email",
        existing_type=sa.String(length=255),
        type_=sa.String(length=512),
        existing_nullable=True,
    )
    # customers.phone: 50 → 256
    op.alter_column(
        "customers", "phone",
        existing_type=sa.String(length=50),
        type_=sa.String(length=256),
        existing_nullable=True,
    )
    # customers.whatsapp_number: 50 → 256
    op.alter_column(
        "customers", "whatsapp_number",
        existing_type=sa.String(length=50),
        type_=sa.String(length=256),
        existing_nullable=True,
    )
    # customers.address: 500 → 1024
    op.alter_column(
        "customers", "address",
        existing_type=sa.String(length=500),
        type_=sa.String(length=1024),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Only safe to downsize if NO row contains encrypted data. The
    # operator is expected to run a decrypt-and-rewrite backfill first;
    # otherwise this migration will fail on rows whose ciphertext is
    # longer than the target width, which is the correct outcome.
    op.alter_column(
        "customers", "address",
        existing_type=sa.String(length=1024),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
    op.alter_column(
        "customers", "whatsapp_number",
        existing_type=sa.String(length=256),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.alter_column(
        "customers", "phone",
        existing_type=sa.String(length=256),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.alter_column(
        "customers", "email",
        existing_type=sa.String(length=512),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "auth_users", "totp_secret",
        existing_type=sa.String(length=512),
        type_=sa.String(length=64),
        existing_nullable=True,
    )
