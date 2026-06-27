"""Add CHECK constraints on invoice_line_items and payments (L3)

Revision ID: f0e1d2c3b4a5
Revises: 67779050fa82
Create Date: 2026-06-16

"""
from typing import Sequence, Union

from alembic import op

revision: str = "f0e1d2c3b4a5"
down_revision: Union[str, None] = "67779050fa82"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_invoice_line_item_quantity_positive",
        "invoice_line_items",
        "quantity > 0",
    )
    op.create_check_constraint(
        "ck_invoice_line_item_unit_price_non_negative",
        "invoice_line_items",
        "unit_price >= 0",
    )
    op.create_check_constraint(
        "ck_invoice_line_item_tax_rate_range",
        "invoice_line_items",
        "tax_rate >= 0 AND tax_rate <= 100",
    )
    op.create_check_constraint(
        "ck_payment_amount_positive",
        "payments",
        "amount > 0",
    )
    op.create_check_constraint(
        "ck_payment_exchange_rate_positive",
        "payments",
        "exchange_rate > 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_payment_exchange_rate_positive", "payments")
    op.drop_constraint("ck_payment_amount_positive", "payments")
    op.drop_constraint("ck_invoice_line_item_tax_rate_range", "invoice_line_items")
    op.drop_constraint("ck_invoice_line_item_unit_price_non_negative", "invoice_line_items")
    op.drop_constraint("ck_invoice_line_item_quantity_positive", "invoice_line_items")
