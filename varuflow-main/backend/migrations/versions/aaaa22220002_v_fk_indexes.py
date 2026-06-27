"""v_fk_indexes: add missing FK indexes across pos, inventory, invoicing models.

Revision ID: aaaa22220002
Revises: 6005c017b2f6
Create Date: 2026-06-10

CLAUDE.md Rule 5: every FK column must have a DB-level index.
This migration adds indexes that were missing from pos_sales, pos_sale_items,
stock_levels, stock_movements, purchase_orders, purchase_order_items,
product_batches, recurring_invoices, and invoices.

All indexes are created with if_not_exists=True so the migration is safe
to run against a DB where a DBA has already added one manually.
"""
from alembic import op

revision = "aaaa22220002"
down_revision = "6005c017b2f6"
branch_labels = None
depends_on = None

_INDEXES = [
    # ── POS ──────────────────────────────────────────────────────────────────
    # pos_sales — session_id is the primary join key for "list sales in session"
    ("ix_pos_sales_session_id",                  "pos_sales",              ["session_id"]),
    # pos_sales — staff_id for commission-by-staff reporting
    ("ix_pos_sales_staff_id",                    "pos_sales",              ["staff_id"]),
    # pos_sale_items — sale_id is always in WHERE when loading a sale's lines
    ("ix_pos_sale_items_sale_id",                "pos_sale_items",         ["sale_id"]),
    # pos_sale_items — product_id for product-level sales analytics
    ("ix_pos_sale_items_product_id",             "pos_sale_items",         ["product_id"]),

    # ── Inventory ─────────────────────────────────────────────────────────────
    # stock_levels — product_id + warehouse_id are the two join axes
    ("ix_stock_levels_product_id",               "stock_levels",           ["product_id"]),
    ("ix_stock_levels_warehouse_id",             "stock_levels",           ["warehouse_id"]),
    # stock_movements — product_id for movement history; warehouse_id for per-location queries
    ("ix_stock_movements_product_id",            "stock_movements",        ["product_id"]),
    ("ix_stock_movements_warehouse_id",          "stock_movements",        ["warehouse_id"]),
    # purchase_orders — supplier_id is the primary filter for "POs by supplier"
    ("ix_purchase_orders_supplier_id",           "purchase_orders",        ["supplier_id"]),
    # purchase_orders — confirmed_by_supplier_id for supplier-portal confirmation lookups
    ("ix_purchase_orders_confirmed_supplier_id", "purchase_orders",        ["confirmed_by_supplier_id"]),
    # purchase_order_items — purchase_order_id is always in WHERE when loading items
    ("ix_purchase_order_items_po_id",            "purchase_order_items",   ["purchase_order_id"]),
    # purchase_order_items — product_id for "which POs include product X" queries
    ("ix_purchase_order_items_product_id",       "purchase_order_items",   ["product_id"]),
    # product_batches — warehouse_id for FEFO picking (scoped to warehouse)
    ("ix_product_batches_warehouse_id",          "product_batches",        ["warehouse_id"]),

    # ── Invoicing ─────────────────────────────────────────────────────────────
    # recurring_invoices — template_invoice_id for "which recurring uses this template" lookup
    ("ix_recurring_invoices_template_invoice_id", "recurring_invoices",    ["template_invoice_id"]),
    # invoices — staff_id for commission reporting
    ("ix_invoices_staff_id",                     "invoices",               ["staff_id"]),
    # invoices — status / due_date for dunning sweep and dashboard filters
    # (present in Supabase SQL initial schema; missing from Alembic chain)
    ("ix_invoices_status",                       "invoices",               ["status"]),
    ("ix_invoices_due_date",                     "invoices",               ["due_date"]),

    # ── BOM ───────────────────────────────────────────────────────────────────
    # bom_lines — org_id for multi-tenant list queries
    ("ix_bom_lines_org_id",                      "bom_lines",              ["org_id"]),

    # ── Schema drift backfill (Supabase SQL has these; Alembic chain did not) ──
    ("ix_stock_movements_product_id_drift",      "stock_movements",        ["product_id"]),
]

# Deduplicated list — ix_stock_movements_product_id appears twice due to drift;
# keep only the canonical name.
_INDEXES_DEDUPED = [
    ("ix_pos_sales_session_id",                   "pos_sales",             ["session_id"]),
    ("ix_pos_sales_staff_id",                     "pos_sales",             ["staff_id"]),
    ("ix_pos_sale_items_sale_id",                 "pos_sale_items",        ["sale_id"]),
    ("ix_pos_sale_items_product_id",              "pos_sale_items",        ["product_id"]),
    ("ix_stock_levels_product_id",                "stock_levels",          ["product_id"]),
    ("ix_stock_levels_warehouse_id",              "stock_levels",          ["warehouse_id"]),
    ("ix_stock_movements_product_id",             "stock_movements",       ["product_id"]),
    ("ix_stock_movements_warehouse_id",           "stock_movements",       ["warehouse_id"]),
    ("ix_purchase_orders_supplier_id",            "purchase_orders",       ["supplier_id"]),
    ("ix_purchase_orders_confirmed_supplier_id",  "purchase_orders",       ["confirmed_by_supplier_id"]),
    ("ix_purchase_order_items_po_id",             "purchase_order_items",  ["purchase_order_id"]),
    ("ix_purchase_order_items_product_id",        "purchase_order_items",  ["product_id"]),
    ("ix_product_batches_warehouse_id",           "product_batches",       ["warehouse_id"]),
    ("ix_recurring_invoices_template_invoice_id", "recurring_invoices",    ["template_invoice_id"]),
    ("ix_invoices_staff_id",                      "invoices",              ["staff_id"]),
    ("ix_invoices_status",                        "invoices",              ["status"]),
    ("ix_invoices_due_date",                      "invoices",              ["due_date"]),
    ("ix_bom_lines_org_id",                       "bom_lines",             ["org_id"]),
]


def upgrade() -> None:
    for name, table, cols in _INDEXES_DEDUPED:
        op.create_index(name, table, cols, if_not_exists=True)


def downgrade() -> None:
    for name, table, _ in reversed(_INDEXES_DEDUPED):
        op.drop_index(name, table_name=table, if_exists=True)
