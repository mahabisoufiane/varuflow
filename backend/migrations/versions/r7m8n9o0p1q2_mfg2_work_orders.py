"""mfg2 — work_orders, work_order_material_lines, work_order_labour_lines

Revision ID: r7m8n9o0p1q2
Revises:     q6l7m8n9o0p1
Create Date: 2026-04-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "r7m8n9o0p1q2"
down_revision = "q6l7m8n9o0p1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bom_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("bom_headers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_number", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("planned_qty", sa.Integer, nullable=False, server_default="1"),
        sa.Column("produced_qty", sa.Integer, nullable=False, server_default="0"),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_id", "order_number", name="uq_work_orders_org_number"),
    )
    op.create_index("ix_work_orders_org_id", "work_orders", ["org_id"])
    op.create_index("ix_work_orders_bom_id", "work_orders", ["bom_id"])
    op.create_index("ix_work_orders_status", "work_orders", ["status"])

    op.create_table(
        "work_order_material_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("work_order_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("planned_qty", sa.Numeric(12, 4), nullable=False),
        sa.Column("actual_qty", sa.Numeric(12, 4), nullable=True),
        sa.Column("unit", sa.String(50), nullable=False, server_default="st"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_work_order_material_lines_work_order_id", "work_order_material_lines", ["work_order_id"])

    op.create_table(
        "work_order_labour_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("work_order_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("operator_name", sa.String(255), nullable=False),
        sa.Column("hours", sa.Numeric(6, 2), nullable=False),
        sa.Column("hourly_rate", sa.Numeric(10, 2), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_work_order_labour_lines_work_order_id", "work_order_labour_lines", ["work_order_id"])


def downgrade() -> None:
    op.drop_table("work_order_labour_lines")
    op.drop_table("work_order_material_lines")
    op.drop_table("work_orders")
