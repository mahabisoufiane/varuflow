"""v95 — Recurring expense templates (Item 97).

A `RecurringExpenseTemplate` mints an `Expense` on a cadence
(daily / weekly / monthly / yearly). The row owns the recurrence
metadata (cadence + interval + next_due + last_generated_at +
is_active) and the payload that gets copied into the emitted
expense (category, amount, currency, description, supplier_id).

Revision: a4b6c8d0e2f7
Revises:  f2a4b6c8d0e5 (v94 — expense tags, Item 95)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a4b6c8d0e2f7"
down_revision = "f2a4b6c8d0e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    cadence = sa.Enum(
        "DAILY", "WEEKLY", "MONTHLY", "YEARLY",
        name="recurring_expense_cadence",
    )
    cadence.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "recurring_expense_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column(
            "category_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expense_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "supplier_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "currency", sa.String(length=3),
            nullable=False, server_default="SEK",
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "cadence", cadence, nullable=False,
        ),
        sa.Column(
            "interval_count", sa.Integer(), nullable=False,
            server_default="1",
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("next_due_date", sa.Date(), nullable=False),
        sa.Column(
            "last_generated_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "last_generated_expense_id", postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("generated_count", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False,
            server_default=sa.text("true"),
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
        "ix_recurring_expense_templates_org_id",
        "recurring_expense_templates", ["org_id"],
    )
    # Hot scheduler query: "all active templates whose next_due
    # has landed" — sorted by due date.
    op.create_index(
        "ix_recurring_expense_templates_active_due",
        "recurring_expense_templates",
        ["is_active", "next_due_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recurring_expense_templates_active_due",
        table_name="recurring_expense_templates",
    )
    op.drop_index(
        "ix_recurring_expense_templates_org_id",
        table_name="recurring_expense_templates",
    )
    op.drop_table("recurring_expense_templates")
    sa.Enum(name="recurring_expense_cadence").drop(
        op.get_bind(), checkfirst=True,
    )
