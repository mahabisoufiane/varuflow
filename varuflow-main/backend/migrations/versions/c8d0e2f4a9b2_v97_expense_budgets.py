"""v97 — Expense budgets (Item 99).

An `expense_budget` is a per-category, per-period cap
(e.g. Travel / 2026-04 / 10000 SEK). Live spend is rolled up on
read from the `expenses` table; we do not denormalise the running
total — a scheduled job would drift, and budget reads are rare
compared to expense writes.

Revision: c8d0e2f4a9b2
Revises:  b6c8d0e2f4a9 (v96 — mileage logs, Item 98)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c8d0e2f4a9b2"
down_revision = "b6c8d0e2f4a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    period = sa.Enum(
        "MONTH", "QUARTER", "YEAR",
        name="expense_budget_period",
    )

    op.create_table(
        "expense_budgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "category_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expense_categories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period", period, nullable=False),
        # ``period_start`` anchors the window. The service module
        # computes the matching end from ``period`` so we don't have
        # to denormalise it.
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("amount_cap", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "currency", sa.String(length=3),
            nullable=False, server_default="SEK",
        ),
        sa.Column(
            "alert_threshold_pct", sa.Integer(),
            nullable=False, server_default="80",
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_by_user_id", postgresql.UUID(as_uuid=True),
            nullable=False,
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
        "ix_expense_budgets_org_id",
        "expense_budgets", ["org_id"],
    )
    # One budget per (org, category, period, period_start). Avoids
    # the "two Travel April caps" ambiguity.
    op.create_index(
        "ux_expense_budgets_org_cat_period_start",
        "expense_budgets",
        ["org_id", "category_id", "period", "period_start"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ux_expense_budgets_org_cat_period_start",
        table_name="expense_budgets",
    )
    op.drop_index(
        "ix_expense_budgets_org_id",
        table_name="expense_budgets",
    )
    op.drop_table("expense_budgets")
    sa.Enum(name="expense_budget_period").drop(
        op.get_bind(), checkfirst=True,
    )
