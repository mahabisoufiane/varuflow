"""v63 — Product variants (Item 53).

A product can have zero or many variants (e.g. size, color, weight).
When variants exist, stock is tracked per variant rather than on the
parent product row. The parent keeps the marketing-facing metadata
(name, category, description) while each variant carries its own
SKU, barcode, optional price override, and attribute map.

Two tables:

* ``product_variants`` — one row per purchasable SKU under a product.
  ``attributes`` is JSONB so each product family can define its own
  keys (``{"size": "M", "color": "blue"}``) without a migration.
* ``variant_stock_levels`` — per-(variant, warehouse) quantity.
  Parallels the existing ``stock_levels`` table; we don't retrofit
  it to point at variants because not every product becomes variant
  -bearing, and retrofits would break Item 21's constraints.

Invoice / POS line FKs are unchanged — they still reference the
parent product, with an added optional ``variant_id`` column added
in Item 81+ (Appointment Package Booking) if needed.

Revision: e3f5a7b9c1d5
Revises:  d2e4f6a8b0c3 (v62 — portal OTP, Item 51)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e3f5a7b9c1d5"
down_revision = "d2e4f6a8b0c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_variants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sku", sa.String(length=100), nullable=False),
        sa.Column("barcode", sa.String(length=50), nullable=True),
        sa.Column(
            "attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("sell_price_override", sa.Numeric(12, 2), nullable=True),
        sa.Column("purchase_price_override", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("org_id", "sku", name="uq_product_variants_org_sku"),
    )
    op.create_index(
        "ix_product_variants_product",
        "product_variants",
        ["product_id"],
    )
    op.create_index(
        "ix_product_variants_org",
        "product_variants",
        ["org_id"],
    )

    op.create_table(
        "variant_stock_levels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "variant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_variants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "warehouse_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "variant_id",
            "warehouse_id",
            name="uq_variant_stock_levels_variant_warehouse",
        ),
    )
    op.create_index(
        "ix_variant_stock_levels_org",
        "variant_stock_levels",
        ["org_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_variant_stock_levels_org", table_name="variant_stock_levels")
    op.drop_table("variant_stock_levels")
    op.drop_index("ix_product_variants_org", table_name="product_variants")
    op.drop_index("ix_product_variants_product", table_name="product_variants")
    op.drop_table("product_variants")
