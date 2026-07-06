"""purchase request urgency and budget category

Revision ID: tt0uu1vv2ww3
Revises: ss9tt0uu1vv2
Create Date: 2026-05-01

"""
from alembic import op
import sqlalchemy as sa

revision = "tt0uu1vv2ww3"
down_revision = "ss9tt0uu1vv2"
branch_labels = None
# cross-branch ordering: purchase_requests live on parallel branches — apply first
depends_on = "cc2dd3ee4ff5"
def upgrade() -> None:
    op.add_column("purchase_requests", sa.Column("urgency", sa.String(20), nullable=True, server_default="normal"))
    op.add_column("purchase_requests", sa.Column("budget_category", sa.String(100), nullable=True))
    op.add_column("purchase_requests", sa.Column("budget_exceeded", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("purchase_requests", sa.Column("is_template", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("purchase_requests", sa.Column("template_name", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("purchase_requests", "template_name")
    op.drop_column("purchase_requests", "is_template")
    op.drop_column("purchase_requests", "budget_exceeded")
    op.drop_column("purchase_requests", "budget_category")
    op.drop_column("purchase_requests", "urgency")
