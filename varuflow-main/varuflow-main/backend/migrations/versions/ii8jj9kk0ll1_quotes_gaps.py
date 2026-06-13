"""quotes: add decline_reason, public_token; track viewed status

Revision ID: ii8jj9kk0ll1
Revises: hh7ii8jj9kk0
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa

revision = "ii8jj9kk0ll1"
down_revision = "hh7ii8jj9kk0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # decline_reason: stored when a prospect declines a quote,
    # either via the public token URL or the portal.
    op.add_column("quotes", sa.Column("decline_reason", sa.Text(), nullable=True))

    # public_token: 64-char hex token used to build the publicly
    # shareable quote URL (/q/{token}) — no portal login required.
    # Generated at quote creation time.  Unique across all quotes.
    op.add_column("quotes", sa.Column("public_token", sa.String(64), nullable=True))

    # Backfill: every existing quote gets a unique token derived from
    # its UUID so the column can eventually be set NOT NULL.
    op.execute(
        "UPDATE quotes SET public_token = encode(sha256(id::text::bytea), 'hex') "
        "WHERE public_token IS NULL"
    )

    op.create_unique_constraint("uq_quotes_public_token", "quotes", ["public_token"])


def downgrade() -> None:
    op.drop_constraint("uq_quotes_public_token", "quotes", type_="unique")
    op.drop_column("quotes", "public_token")
    op.drop_column("quotes", "decline_reason")
