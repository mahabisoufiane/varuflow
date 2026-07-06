"""v98 — Expense reports (Item 100).

An `expense_report` groups approved expenses into a single
reimbursable batch. Lifecycle:

    DRAFT → SUBMITTED → APPROVED → PAID
                              ↘ REJECTED (returns to DRAFT-editable)

The owner (ADMIN / OWNER role) reviews the report; once APPROVED,
the PAID transition records payout metadata (paid_at, reference).
The join table `expense_report_items` enforces one report per
expense via a unique index on ``expense_id`` — you cannot charge
the same expense to two reports.

Revision: d0e2f4a9b2c5
Revises:  c8d0e2f4a9b2 (v97 — expense budgets, Item 99)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d0e2f4a9b2c5"
down_revision = "c8d0e2f4a9b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    rstatus = sa.Enum(
        "DRAFT", "SUBMITTED", "APPROVED", "REJECTED", "PAID",
        name="expense_report_status",
    )

    op.create_table(
        "expense_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id", postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "currency", sa.String(length=3), nullable=False,
            server_default="SEK",
        ),
        sa.Column(
            "status", rstatus, nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "submitted_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "decided_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "decided_by_user_id", postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column(
            "paid_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column("paid_reference", sa.String(length=120), nullable=True),
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
        "ix_expense_reports_org_id",
        "expense_reports", ["org_id"],
    )
    # Hot query: "my open reports, newest first".
    op.create_index(
        "ix_expense_reports_org_status_created",
        "expense_reports", ["org_id", "status", "created_at"],
    )

    op.create_table(
        "expense_report_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "report_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expense_reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "expense_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expenses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "added_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
    )
    # An expense can appear in at most one report.
    op.create_index(
        "ux_expense_report_items_expense_id",
        "expense_report_items", ["expense_id"], unique=True,
    )
    op.create_index(
        "ix_expense_report_items_report_id",
        "expense_report_items", ["report_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_expense_report_items_report_id",
        table_name="expense_report_items",
    )
    op.drop_index(
        "ux_expense_report_items_expense_id",
        table_name="expense_report_items",
    )
    op.drop_table("expense_report_items")
    op.drop_index(
        "ix_expense_reports_org_status_created",
        table_name="expense_reports",
    )
    op.drop_index(
        "ix_expense_reports_org_id",
        table_name="expense_reports",
    )
    op.drop_table("expense_reports")
    sa.Enum(name="expense_report_status").drop(
        op.get_bind(), checkfirst=True,
    )
