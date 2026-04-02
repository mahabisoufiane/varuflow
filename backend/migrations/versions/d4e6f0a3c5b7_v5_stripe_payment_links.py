"""v5_stripe_payment_links

Revision ID: d4e6f0a3c5b7
Revises: c3d5e9f2b4a6
Create Date: 2026-04-02 13:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e6f0a3c5b7"
down_revision: Union[str, None] = "c3d5e9f2b4a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("stripe_payment_link_url", sa.String(length=500), nullable=True))
    op.add_column("invoices", sa.Column("stripe_payment_link_status", sa.String(length=20), nullable=True))
    op.add_column("invoices", sa.Column("stripe_checkout_session_id", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("invoices", "stripe_checkout_session_id")
    op.drop_column("invoices", "stripe_payment_link_status")
    op.drop_column("invoices", "stripe_payment_link_url")
