"""v16: unique (org_id, sale_number) on pos_sales

Revision ID: b4c6d8e0f2a5
Revises: a3b5c7d9e1f4
Create Date: 2026-04-22

Companion to v15 (invoice number uniqueness). Same class of bug: POS sale
numbers (``POS-YYYYMMDD-NNNN``) are generated from an unlocked
``SELECT COUNT(*)``. Two concurrent checkouts at the same till (happens
whenever a cashier double-taps "confirm") can mint identical sale numbers.

The application now serialises on the Organization row first (see
``backend/app/routers/pos.py``). This migration adds the DB-level
uniqueness so the constraint is still enforced on paths the row-lock
doesn't cover (direct SQL, future callers, etc.).
"""
from alembic import op

revision = "b4c6d8e0f2a5"
down_revision = "a3b5c7d9e1f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename any pre-existing duplicates so the DDL succeeds.
    op.execute("""
        WITH ranked AS (
            SELECT
                id,
                org_id,
                sale_number,
                ROW_NUMBER() OVER (
                    PARTITION BY org_id, sale_number
                    ORDER BY created_at, id
                ) AS rn
            FROM pos_sales
        )
        UPDATE pos_sales s
        SET sale_number = s.sale_number || '-dup-' || substr(s.id::text, 1, 8)
        FROM ranked r
        WHERE s.id = r.id
          AND r.rn > 1
    """)
    op.create_unique_constraint(
        "uq_pos_sales_org_sale_number",
        "pos_sales",
        ["org_id", "sale_number"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_pos_sales_org_sale_number",
        "pos_sales",
        type_="unique",
    )
