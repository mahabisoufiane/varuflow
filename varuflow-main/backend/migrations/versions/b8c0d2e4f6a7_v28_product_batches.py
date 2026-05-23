"""v28: product_batches + batch_id on stock_movements

Revision ID: b8c0d2e4f6a7
Revises: a7b9c1d3e5f6
Create Date: 2026-04-23

Adds lot-level expiry tracking. Each IN movement recorded against a
purchase-order receipt can now register a batch with a batch_number
(e.g. "LOT-2026-001") and an expiry_date. OUT movements pick the
oldest-expiry batch first (FEFO) so perishable stock ships before it
spoils — a hard requirement for food/pharma/cosmetics wholesalers who
must document batch traceability to Livsmedelsverket / Läkemedelsverket.

The stock_movements table also gains a nullable ``batch_id`` FK so we
can attribute every OUT (and voluntary IN) to a specific lot. Nullable
to stay backwards-compatible with historical rows and with OUT
movements for products that don't track batches.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b8c0d2e4f6a7"
down_revision = "a7b9c1d3e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_batches",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "warehouse_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("batch_number", sa.String(length=100), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint("quantity >= 0", name="ck_product_batches_quantity_nonneg"),
        # A product cannot have two rows for the same batch_number in the
        # same warehouse — prevents accidental double-registration on PO
        # receipt (common when a user clicks "receive" twice).
        sa.UniqueConstraint(
            "product_id",
            "warehouse_id",
            "batch_number",
            name="uq_product_batches_product_warehouse_batch",
        ),
    )
    op.create_index(
        "ix_product_batches_org_id",
        "product_batches",
        ["org_id"],
    )
    op.create_index(
        "ix_product_batches_product_id",
        "product_batches",
        ["product_id"],
    )
    # FEFO lookups sort by expiry ascending within a (product, warehouse)
    # scope — a partial index speeds up the picker without bloating the
    # table during WMS-heavy days.
    op.create_index(
        "ix_product_batches_fefo",
        "product_batches",
        ["product_id", "warehouse_id", "expiry_date"],
        postgresql_where=sa.text("quantity > 0"),
    )

    op.add_column(
        "stock_movements",
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_batches.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_stock_movements_batch_id",
        "stock_movements",
        ["batch_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_stock_movements_batch_id", table_name="stock_movements")
    op.drop_column("stock_movements", "batch_id")
    op.drop_index("ix_product_batches_fefo", table_name="product_batches")
    op.drop_index("ix_product_batches_product_id", table_name="product_batches")
    op.drop_index("ix_product_batches_org_id", table_name="product_batches")
    op.drop_table("product_batches")
