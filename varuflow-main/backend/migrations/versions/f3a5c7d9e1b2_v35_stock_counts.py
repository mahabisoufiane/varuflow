"""v35: stock_counts + stock_count_items (Item 14 — offline cycle counts)

Revision ID: f3a5c7d9e1b2
Revises: e1f3a5b7c9d4
Create Date: 2026-04-23

Introduces two tables backing the offline stock-count (cycle count)
workflow. Drafts live on the device in AsyncStorage; once the user
taps *Submit* and the device is online, each count is POSTed here.
The server compares counted_qty against the live StockLevel and —
per item — creates an ADJUSTMENT ``StockMovement`` equal to the
variance, so physical counts never bypass the stock ledger.

Idempotency: the client supplies row UUIDs. Repeated submissions of
the same count id are no-ops (the router checks status before creating
adjustment movements).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f3a5c7d9e1b2"
down_revision = "e1f3a5b7c9d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    stock_count_status = postgresql.ENUM(
        "DRAFT",
        "SUBMITTED",
        "SYNCED",
        "CANCELLED",
        name="stock_count_status",
        create_type=True,
    )
    stock_count_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "stock_counts",
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
            "warehouse_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            # postgresql.ENUM (not sa.Enum) so create_type=False is honored —
            # the type is pre-created above via .create(checkfirst=True). With
            # the generic sa.Enum, create_type is ignored and create_table
            # re-emits CREATE TYPE, failing with DuplicateObjectError.
            postgresql.ENUM(
                "DRAFT",
                "SUBMITTED",
                "SYNCED",
                "CANCELLED",
                name="stock_count_status",
                create_type=False,
            ),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_stock_counts_org_id", "stock_counts", ["org_id"])
    op.create_index(
        "ix_stock_counts_warehouse_id", "stock_counts", ["warehouse_id"]
    )
    op.create_index("ix_stock_counts_status", "stock_counts", ["status"])

    op.create_table(
        "stock_count_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "stock_count_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stock_counts.id", ondelete="CASCADE"),
            nullable=False,
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
            "batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_batches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("expected_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("counted_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("variance_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_stock_count_items_stock_count_id",
        "stock_count_items",
        ["stock_count_id"],
    )
    op.create_index(
        "ix_stock_count_items_org_id", "stock_count_items", ["org_id"]
    )
    op.create_index(
        "ix_stock_count_items_product_id",
        "stock_count_items",
        ["product_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stock_count_items_product_id", table_name="stock_count_items"
    )
    op.drop_index("ix_stock_count_items_org_id", table_name="stock_count_items")
    op.drop_index(
        "ix_stock_count_items_stock_count_id", table_name="stock_count_items"
    )
    op.drop_table("stock_count_items")

    op.drop_index("ix_stock_counts_status", table_name="stock_counts")
    op.drop_index("ix_stock_counts_warehouse_id", table_name="stock_counts")
    op.drop_index("ix_stock_counts_org_id", table_name="stock_counts")
    op.drop_table("stock_counts")

    postgresql.ENUM(name="stock_count_status").drop(op.get_bind(), checkfirst=True)
