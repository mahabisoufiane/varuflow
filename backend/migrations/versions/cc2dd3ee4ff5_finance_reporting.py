"""finance_reporting — Finance Visibility + Reporting tables.

Revision ID: cc2dd3ee4ff5
Revises: bb1cc2dd3ee4
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "cc2dd3ee4ff5"
down_revision = "bb1cc2dd3ee4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- ALTER expense_budgets: add owner + department --
    op.add_column("expense_budgets", sa.Column("owner_staff_id", UUID(as_uuid=True), sa.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True))
    op.add_column("expense_budgets", sa.Column("department", sa.String(100), nullable=True))
    op.create_index("ix_expense_budgets_owner", "expense_budgets", ["org_id", "owner_staff_id"])

    # -- ALTER mileage_logs: add approval --
    op.add_column("mileage_logs", sa.Column("approval_status", sa.String(10), nullable=False, server_default="pending"))
    op.add_column("mileage_logs", sa.Column("approved_by", UUID(as_uuid=True), sa.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True))
    op.add_column("mileage_logs", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))

    # -- ALTER project_time_entries: add approval --
    op.add_column("project_time_entries", sa.Column("approval_status", sa.String(10), nullable=False, server_default="pending"))
    op.add_column("project_time_entries", sa.Column("approved_by", UUID(as_uuid=True), sa.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True))
    op.add_column("project_time_entries", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))

    # -- purchase_requests --
    op.create_table(
        "purchase_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by", UUID(as_uuid=True), sa.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("estimated_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", UUID(as_uuid=True), sa.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("purchase_order_id", UUID(as_uuid=True), sa.ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_purchase_requests_org", "purchase_requests", ["org_id"])
    op.create_index("ix_purchase_requests_status", "purchase_requests", ["org_id", "status"])

    # -- purchase_request_items --
    op.create_table(
        "purchase_request_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("purchase_request_id", UUID(as_uuid=True), sa.ForeignKey("purchase_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
    )

    # -- petty_cash_transactions --
    op.create_table(
        "petty_cash_transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("txn_date", sa.Date(), nullable=False),
        sa.Column("txn_type", sa.String(10), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("receipt_url", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_petty_cash_org", "petty_cash_transactions", ["org_id"])
    op.create_index("ix_petty_cash_org_date", "petty_cash_transactions", ["org_id", "txn_date"])


def downgrade() -> None:
    op.drop_table("petty_cash_transactions")
    op.drop_table("purchase_request_items")
    op.drop_table("purchase_requests")
    op.drop_column("project_time_entries", "approved_at")
    op.drop_column("project_time_entries", "approved_by")
    op.drop_column("project_time_entries", "approval_status")
    op.drop_column("mileage_logs", "approved_at")
    op.drop_column("mileage_logs", "approved_by")
    op.drop_column("mileage_logs", "approval_status")
    op.drop_index("ix_expense_budgets_owner", table_name="expense_budgets")
    op.drop_column("expense_budgets", "department")
    op.drop_column("expense_budgets", "owner_staff_id")
