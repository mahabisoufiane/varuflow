"""sE2 — E-commerce tables (storefronts, online_orders, cart_sessions)

Revision ID: g6b7c8d9e0f1
Revises:     f5a6b7c8d9e0
Create Date: 2026-04-30

Adds:
  storefronts        — per-org public shop (one per org, unique slug)
  online_orders      — customer-placed orders
  online_order_items — line items per order
  cart_sessions      — guest carts for abandoned-cart recovery
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "g6b7c8d9e0f1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "storefronts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("tagline", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("primary_color", sa.String(7), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("payment_methods", sa.String(100), server_default="card", nullable=False),
        sa.Column("currency", sa.String(3), server_default="SEK", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_id", name="uq_storefronts_org_id"),
        sa.UniqueConstraint("slug", name="uq_storefronts_slug"),
    )
    op.create_index("ix_storefronts_slug", "storefronts", ["slug"])

    op.create_table(
        "online_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storefront_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("storefronts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_number", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), server_default="PENDING", nullable=False),
        sa.Column("customer_email", sa.String(255), nullable=False),
        sa.Column("customer_name", sa.String(200), nullable=False),
        sa.Column("shipping_address", postgresql.JSONB(), nullable=True),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("vat_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("shipping_cost", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("stripe_checkout_session_id", sa.String(255), nullable=True),
        sa.Column("stripe_payment_intent_id", sa.String(255), nullable=True),
        sa.Column("payment_method", sa.String(30), nullable=True),
        sa.Column("shipping_carrier", sa.String(30), nullable=True),
        sa.Column("tracking_number", sa.String(100), nullable=True),
        sa.Column("tracking_url", sa.Text(), nullable=True),
        sa.Column("nshift_shipment_id", sa.String(100), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("order_number", name="uq_online_orders_number"),
    )
    op.create_index("ix_online_orders_org_id", "online_orders", ["org_id"])
    op.create_index("ix_online_orders_storefront_id", "online_orders", ["storefront_id"])

    op.create_table(
        "online_order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("online_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
    )
    op.create_index("ix_online_order_items_order_id", "online_order_items", ["order_id"])

    op.create_table(
        "cart_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storefront_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("storefronts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guest_token", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_email", sa.String(255), nullable=True),
        sa.Column("items", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("checkout_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("abandoned_email_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("guest_token", name="uq_cart_sessions_guest_token"),
    )
    op.create_index("ix_cart_sessions_org_id", "cart_sessions", ["org_id"])
    op.create_index("ix_cart_sessions_storefront_id", "cart_sessions", ["storefront_id"])


def downgrade() -> None:
    op.drop_index("ix_cart_sessions_storefront_id", table_name="cart_sessions")
    op.drop_index("ix_cart_sessions_org_id", table_name="cart_sessions")
    op.drop_table("cart_sessions")
    op.drop_index("ix_online_order_items_order_id", table_name="online_order_items")
    op.drop_table("online_order_items")
    op.drop_index("ix_online_orders_storefront_id", table_name="online_orders")
    op.drop_index("ix_online_orders_org_id", table_name="online_orders")
    op.drop_table("online_orders")
    op.drop_index("ix_storefronts_slug", table_name="storefronts")
    op.drop_table("storefronts")
