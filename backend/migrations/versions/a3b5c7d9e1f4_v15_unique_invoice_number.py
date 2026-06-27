"""v15: unique (org_id, invoice_number) on invoices

Revision ID: a3b5c7d9e1f4
Revises: f2a4c6e8d1b3
Create Date: 2026-04-22

Prevents duplicate invoice numbers within the same organization. The
application generates numbers from ``SELECT COUNT(*) WHERE org_id = ...``
which is racy: two concurrent create_invoice calls can both observe the
same count and assign the same INV-YYYY-NNNN sequence. This would:

  • violate Swedish bokföringslagen (each invoice must have a unique
    sequential number), and
  • break client-side invoice lookup that treats invoice_number as a key.

Enforce it at the DB level so the second transaction fails with a
clean IntegrityError that the application can retry.

A plain UNIQUE across invoice_number alone would be wrong — different
tenants legitimately have the same INV-2026-0001. The composite
(org_id, invoice_number) uniqueness matches tenant isolation.
"""
from alembic import op

revision = "a3b5c7d9e1f4"
down_revision = "f2a4c6e8d1b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Dedupe first: if any org somehow ended up with duplicates (shouldn't
    # happen on a freshly-provisioned prod DB but is possible on pre-v15
    # staging data), rename all but the earliest to a suffixed string so
    # the DDL succeeds without data loss.
    op.execute("""
        WITH ranked AS (
            SELECT
                id,
                org_id,
                invoice_number,
                ROW_NUMBER() OVER (
                    PARTITION BY org_id, invoice_number
                    ORDER BY created_at, id
                ) AS rn
            FROM invoices
        )
        UPDATE invoices i
        SET invoice_number = i.invoice_number || '-dup-' || substr(i.id::text, 1, 8)
        FROM ranked r
        WHERE i.id = r.id
          AND r.rn > 1
    """)
    op.create_unique_constraint(
        "uq_invoices_org_invoice_number",
        "invoices",
        ["org_id", "invoice_number"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_invoices_org_invoice_number",
        "invoices",
        type_="unique",
    )
