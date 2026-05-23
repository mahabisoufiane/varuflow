"""v53 — multi-location stock transfers (Item 38).

Adds two tables:

* ``stock_transfers`` — one row per transfer between two warehouses.
  Holds status (DRAFT / IN_TRANSIT / RECEIVED / PARTIAL / CANCELLED),
  audit columns, and the human notes field.
* ``stock_transfer_items`` — line items. Tracks the three qty
  checkpoints: requested at creation, actually shipped, and
  actually received. Differences between requested and shipped /
  received surface shrinkage and damage-in-transit.

Spec asked for v45; v45 is taken by
``c6d8e0f2a4b6_v45_ip_allowlist.py``. Landed at v53, the next free
slot after v52 (supplier portal). Same rationale as §58–§66 shifts.

Revision: e1f2a3b4c5d6
Revises:  d0e1f2a3b4c5 (v52 — supplier portal, Item 37)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


STATUS_ENUM_NAME = "stock_transfer_status"


def upgrade() -> None:
    status_enum = postgresql.ENUM(
        "DRAFT",
        "IN_TRANSIT",
        "PARTIAL",
        "RECEIVED",
        "CANCELLED",
        name=STATUS_ENUM_NAME,
    )
    status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "stock_transfers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_warehouse_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "to_warehouse_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name=STATUS_ENUM_NAME, create_type=False),
            nullable=False,
            server_default="DRAFT",
        ),
        # ``created_by`` is nullable so the seed / test paths that
        # don't thread an auth user still function — production
        # writes always set it from the router.
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("notes", sa.Text, nullable=True),
        # Timestamped checkpoints for the lifecycle. Kept nullable
        # so a fresh DRAFT only carries ``created_at`` and the
        # others fill in as the transfer advances.
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "from_warehouse_id <> to_warehouse_id",
            name="ck_stock_transfers_distinct_warehouses",
        ),
    )
    op.create_index(
        "ix_stock_transfers_org_status",
        "stock_transfers",
        ["org_id", "status", "created_at"],
    )
    op.create_index(
        "ix_stock_transfers_from_wh",
        "stock_transfers",
        ["from_warehouse_id"],
    )
    op.create_index(
        "ix_stock_transfers_to_wh",
        "stock_transfers",
        ["to_warehouse_id"],
    )

    op.create_table(
        "stock_transfer_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "transfer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stock_transfers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # Lot-aware when the caller wants FEFO / expiry trackability
        # (Item 28). Nullable so non-batched products still transfer.
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_batches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "qty_requested",
            sa.Integer,
            nullable=False,
        ),
        sa.Column(
            "qty_shipped",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "qty_received",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.CheckConstraint("qty_requested > 0", name="ck_sti_requested_positive"),
        sa.CheckConstraint("qty_shipped >= 0", name="ck_sti_shipped_nonneg"),
        sa.CheckConstraint("qty_received >= 0", name="ck_sti_received_nonneg"),
        sa.CheckConstraint(
            "qty_shipped <= qty_requested",
            name="ck_sti_shipped_le_requested",
        ),
        sa.CheckConstraint(
            "qty_received <= qty_shipped",
            name="ck_sti_received_le_shipped",
        ),
    )
    op.create_index(
        "ix_stock_transfer_items_transfer",
        "stock_transfer_items",
        ["transfer_id"],
    )
    op.create_index(
        "ix_stock_transfer_items_product",
        "stock_transfer_items",
        ["product_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_stock_transfer_items_product", table_name="stock_transfer_items",
    )
    op.drop_index(
        "ix_stock_transfer_items_transfer", table_name="stock_transfer_items",
    )
    op.drop_table("stock_transfer_items")
    op.drop_index("ix_stock_transfers_to_wh", table_name="stock_transfers")
    op.drop_index("ix_stock_transfers_from_wh", table_name="stock_transfers")
    op.drop_index("ix_stock_transfers_org_status", table_name="stock_transfers")
    op.drop_table("stock_transfers")
    sa.Enum(name=STATUS_ENUM_NAME).drop(op.get_bind(), checkfirst=True)
