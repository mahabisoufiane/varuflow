"""return request photo url

Revision ID: pp6qq7rr8ss9
Revises: oo5pp6qq7rr8
Create Date: 2026-04-30

"""
from alembic import op
import sqlalchemy as sa

revision = "pp6qq7rr8ss9"
down_revision = "oo5pp6qq7rr8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("return_requests", sa.Column("photo_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("return_requests", "photo_url")
