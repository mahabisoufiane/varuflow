"""v3_pos_barcode

Revision ID: b2c4d8f1a3e5
Revises: 957ae9166078
Create Date: 2026-04-02 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c4d8f1a3e5"
down_revision: Union[str, None] = "957ae9166078"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Stripe customer id on organizations
    op.add_column("organizations", sa.Column("stripe_customer_id", sa.String(length=100), nullable=True))

    # Barcode column on products
    op.add_column("products", sa.Column("barcode", sa.String(length=50), nullable=True))
    op.create_index("ix_products_barcode", "products", ["barcode"])

    # POS enums
    op.execute("CREATE TYPE pos_session_status AS ENUM ('OPEN', 'CLOSED')")
    op.execute("CREATE TYPE pos_payment_method AS ENUM ('CASH', 'CARD', 'SWISH', 'OTHER')")

    # pos_sessions — raw SQL avoids SQLAlchemy double-creating the enum types
    op.execute("""
        CREATE TABLE pos_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            cashier_user_id UUID NOT NULL,
            status pos_session_status NOT NULL DEFAULT 'OPEN',
            opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            closed_at TIMESTAMPTZ,
            notes TEXT
        )
    """)
    op.execute("CREATE INDEX ix_pos_sessions_org_id ON pos_sessions (org_id)")

    # pos_sales
    op.execute("""
        CREATE TABLE pos_sales (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            session_id UUID NOT NULL REFERENCES pos_sessions(id) ON DELETE CASCADE,
            sale_number VARCHAR(50) NOT NULL,
            subtotal NUMERIC(14,2) NOT NULL DEFAULT 0.00,
            vat_amount NUMERIC(14,2) NOT NULL DEFAULT 0.00,
            total NUMERIC(14,2) NOT NULL,
            payment_method pos_payment_method NOT NULL DEFAULT 'CASH',
            amount_tendered NUMERIC(14,2),
            change_due NUMERIC(14,2),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ix_pos_sales_org_id ON pos_sales (org_id)")

    # pos_sale_items
    op.execute("""
        CREATE TABLE pos_sale_items (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sale_id UUID NOT NULL REFERENCES pos_sales(id) ON DELETE CASCADE,
            product_id UUID REFERENCES products(id) ON DELETE SET NULL,
            description VARCHAR(255) NOT NULL,
            quantity NUMERIC(10,3) NOT NULL,
            unit_price NUMERIC(12,2) NOT NULL,
            tax_rate NUMERIC(5,2) NOT NULL DEFAULT 25.00,
            line_total NUMERIC(14,2) NOT NULL
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pos_sale_items")
    op.execute("DROP TABLE IF EXISTS pos_sales")
    op.execute("DROP TABLE IF EXISTS pos_sessions")
    op.execute("DROP TYPE IF EXISTS pos_payment_method")
    op.execute("DROP TYPE IF EXISTS pos_session_status")
    op.drop_index("ix_products_barcode", table_name="products")
    op.drop_column("products", "barcode")
    op.drop_column("organizations", "stripe_customer_id")
