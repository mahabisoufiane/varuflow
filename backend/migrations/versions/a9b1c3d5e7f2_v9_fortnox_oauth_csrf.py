"""v9: fortnox_oauth_states table for CSRF protection

Revision ID: a9b1c3d5e7f2
Revises: b3c5e9f1a2d4
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "a9b1c3d5e7f2"
down_revision = "b3c5e9f1a2d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fortnox_oauth_states",
        sa.Column("id",         UUID(as_uuid=True), primary_key=True),
        sa.Column("nonce",      sa.String(64),      nullable=False),
        sa.Column("org_id",     UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_fortnox_oauth_states_nonce",  "fortnox_oauth_states", ["nonce"],  unique=True)
    op.create_index("ix_fortnox_oauth_states_org_id", "fortnox_oauth_states", ["org_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_fortnox_oauth_states_nonce",  table_name="fortnox_oauth_states")
    op.drop_index("ix_fortnox_oauth_states_org_id", table_name="fortnox_oauth_states")
    op.drop_table("fortnox_oauth_states")
