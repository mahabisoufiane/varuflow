"""v5_fortnox_openai

Revision ID: c3d5e9f2b4a6
Revises: b2c4d8f1a3e5
Create Date: 2026-04-02 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d5e9f2b4a6"
down_revision: Union[str, None] = "b2c4d8f1a3e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("fortnox_access_token", sa.String(length=2000), nullable=True))
    op.add_column("organizations", sa.Column("fortnox_refresh_token", sa.String(length=2000), nullable=True))
    op.add_column("organizations", sa.Column("fortnox_token_expiry", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "fortnox_token_expiry")
    op.drop_column("organizations", "fortnox_refresh_token")
    op.drop_column("organizations", "fortnox_access_token")
