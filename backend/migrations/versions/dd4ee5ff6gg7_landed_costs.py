"""landed costs: create landed_cost_charges and landed_cost_lines tables

Revision ID: dd4ee5ff6gg7
Revises: cc3dd4ee5ff6
Create Date: 2026-05-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "dd4ee5ff6gg7"
down_revision = "cc3dd4ee5ff6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "landed_cost_charges",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purchase_order_id", UUID(as_uuid=True), sa.ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("charge_type", sa.String(40), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("distribution_method", sa.String(20), nullable=False, server_default="by_value"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_applied", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_landed_cost_charges_org_id", "landed_cost_charges", ["org_id"])
    op.create_index("ix_landed_cost_charges_po_id", "landed_cost_charges", ["purchase_order_id"])

    op.create_table(
        "landed_cost_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("charge_id", UUID(as_uuid=True), sa.ForeignKey("landed_cost_charges.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("purchase_order_item_id", UUID(as_uuid=True), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=True),
        sa.Column("unit_weight", sa.Numeric(10, 4), nullable=True),
        sa.Column("item_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("allocated_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("applied_unit_cost", sa.Numeric(14, 2), nullable=True),
    )
    op.create_index("ix_landed_cost_lines_charge_id", "landed_cost_lines", ["charge_id"])
    op.create_index("ix_landed_cost_lines_product_id", "landed_cost_lines", ["product_id"])


def downgrade() -> None:
    op.drop_table("landed_cost_lines")
    op.drop_table("landed_cost_charges")
