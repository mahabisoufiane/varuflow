"""v41: payable invoices + supplier auto-create flag (Item 20).

Adds:

* ``suppliers.create_invoice_on_receipt`` — opt-in flag (default False)
  that lets a merchant flip on auto-creation of a draft payable
  invoice for a given supplier when a PO transitions to RECEIVED.
  Default False so this is a behaviour-preserving migration: existing
  suppliers stay manual until the merchant explicitly enables it.

* ``payable_invoices`` — a separate table (not ``invoices``) for
  supplier bills the org owes. Kept distinct from sales invoices
  because the lifecycles differ (no Peppol send, no dunning, no
  customer side) and conflating them would force every sales-side
  query to filter by direction. The PO link column carries a unique
  constraint so the auto-create path is naturally idempotent — a
  second receive (impossible today, but defence-in-depth) cannot
  insert a duplicate row.
"""
from alembic import op
import sqlalchemy as sa


revision = "e2f4a6b8c0d1"
down_revision = "d1f3a5b7c9e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "suppliers",
        sa.Column(
            "create_invoice_on_receipt",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    op.create_table(
        "payable_invoices",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "supplier_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "purchase_order_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("purchase_orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # DRAFT / APPROVED / PAID / VOID. Stored as varchar (not enum) so
        # downstream Item 21+ extensions don't need a schema migration to
        # add new states.
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'DRAFT'"),
            nullable=False,
        ),
        sa.Column("invoice_number", sa.String(length=100), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default=sa.text("'SEK'")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "purchase_order_id",
            name="uq_payable_invoices_po",
        ),
    )
    op.create_index(
        "ix_payable_invoices_supplier",
        "payable_invoices",
        ["supplier_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_payable_invoices_supplier", table_name="payable_invoices")
    op.drop_table("payable_invoices")
    op.drop_column("suppliers", "create_invoice_on_receipt")
