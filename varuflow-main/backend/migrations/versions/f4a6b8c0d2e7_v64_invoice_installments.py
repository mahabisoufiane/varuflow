"""v64 — Invoice installment plans (Item 54).

Split an invoice's total into a schedule of smaller payments. One
row per scheduled payment. ``paid_amount`` tracks partial payments
so an installment isn't considered paid until its full amount has
been received.

Key design choices:

* Installments are a **view** onto an invoice — the invoice keeps
  its own ``total_sek`` and Stripe payment link. Paying the whole
  invoice in one go still works and closes every installment.
* An installment has its own due date, independent of the invoice's
  ``due_date`` field. The dunning scheduler (Item 26) already reads
  per-row due dates via a join, so no dunning change is needed.
* ``status`` is an enum mirroring the invoice status vocabulary:
  ``scheduled`` / ``partial`` / ``paid`` / ``overdue`` / ``cancelled``.

Revision: f4a6b8c0d2e7
Revises:  e3f5a7b9c1d5 (v63 — product variants, Item 53)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f4a6b8c0d2e7"
down_revision = "e3f5a7b9c1d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoice_installments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("amount_sek", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "paid_amount_sek",
            sa.Numeric(14, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="scheduled",
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reminded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "invoice_id",
            "sequence",
            name="uq_invoice_installments_invoice_sequence",
        ),
    )
    op.create_index(
        "ix_invoice_installments_invoice",
        "invoice_installments",
        ["invoice_id"],
    )
    op.create_index(
        "ix_invoice_installments_org",
        "invoice_installments",
        ["org_id"],
    )
    op.create_index(
        "ix_invoice_installments_due",
        "invoice_installments",
        ["due_date"],
        postgresql_where=sa.text("status IN ('scheduled', 'partial', 'overdue')"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_invoice_installments_due", table_name="invoice_installments"
    )
    op.drop_index(
        "ix_invoice_installments_org", table_name="invoice_installments"
    )
    op.drop_index(
        "ix_invoice_installments_invoice", table_name="invoice_installments"
    )
    op.drop_table("invoice_installments")
