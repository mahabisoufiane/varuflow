"""v24: BankID personalnummer on auth_users

Revision ID: d4f6a8c0e1b2
Revises: c3e5a7b9d1f2
Create Date: 2026-04-22

Adds a hashed Swedish personal identity number column so BankID-
authenticated logins can look up existing accounts without ever
storing the plaintext personnummer (which is PII and falls under
GDPR as well as the Swedish Folkbokföringslagen confidentiality
regime). The value is SHA-256 of the 12-digit format "YYYYMMDDNNNN".

Unique index so two accounts can never collide on the same person.
Nullable because the column is only populated for users who signed
in through BankID; password/email signups keep it NULL.
"""
from alembic import op
import sqlalchemy as sa

revision = "d4f6a8c0e1b2"
down_revision = "c3e5a7b9d1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "auth_users",
        sa.Column("personalnummer_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_auth_users_personalnummer_hash",
        "auth_users",
        ["personalnummer_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_auth_users_personalnummer_hash", table_name="auth_users")
    op.drop_column("auth_users", "personalnummer_hash")
