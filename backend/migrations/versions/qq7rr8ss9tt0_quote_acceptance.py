"""quote acceptance name and ip

Revision ID: qq7rr8ss9tt0
Revises: pp6qq7rr8ss9
Create Date: 2026-04-30

"""
from alembic import op
import sqlalchemy as sa

revision = "qq7rr8ss9tt0"
down_revision = "pp6qq7rr8ss9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("quotes", sa.Column("acceptance_name", sa.String(200), nullable=True))
    op.add_column("quotes", sa.Column("acceptance_ip", sa.String(45), nullable=True))
    op.add_column("quotes", sa.Column("change_request_comment", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("quotes", "change_request_comment")
    op.drop_column("quotes", "acceptance_ip")
    op.drop_column("quotes", "acceptance_name")
