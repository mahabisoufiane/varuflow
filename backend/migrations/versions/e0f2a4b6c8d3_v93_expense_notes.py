"""v93 — Expense notes (Item 94).

Threaded text notes attached to an expense. Each note carries its
author and can be pinned (bubbled to the top of the expense
detail). Used by finance staff to track approval rationale,
reimbursement disputes, receipt-missing chases, etc.

Mirror of supplier_notes (Item 76, v81) and the earlier note
families (customer, product, warehouse, invoice, purchase-order).

Revision: e0f2a4b6c8d3
Revises:  d8e0f2a6b4c1 (v92 — supplier credit notes, Item 92)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e0f2a4b6c8d3"
down_revision = "d8e0f2a6b4c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "expense_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "expense_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expenses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_user_id", postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "is_pinned", sa.Boolean(),
            nullable=False, server_default=sa.false(),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_expense_notes_org_id", "expense_notes", ["org_id"],
    )
    # Hot-query index — the expense detail sorts pinned first then
    # newest first, filtered by expense_id. A composite over the
    # exact sort keys lets Postgres stream results without a sort
    # step.
    op.create_index(
        "ix_expense_notes_expense_pin_created",
        "expense_notes",
        ["expense_id", "is_pinned", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_expense_notes_expense_pin_created",
        table_name="expense_notes",
    )
    op.drop_index(
        "ix_expense_notes_org_id", table_name="expense_notes",
    )
    op.drop_table("expense_notes")
