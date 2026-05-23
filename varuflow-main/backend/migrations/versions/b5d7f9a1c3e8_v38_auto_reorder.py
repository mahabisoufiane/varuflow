"""v38: auto-reorder org + product columns, auto_reorder_runs table (Item 16)

Revision ID: b5d7f9a1c3e8
Revises: f3a5c7d9e1b2
Create Date: 2026-04-23

Adds the storage backing the auto-reorder purchase-order workflow:

* Per-org switches: ``auto_reorder_enabled``, ``auto_reorder_time``,
  ``auto_reorder_days``, ``auto_reorder_notify_email``. Disabled by
  default so new tenants never have draft POs silently appearing on
  the morning after signup.
* Per-product overrides: ``auto_reorder_enabled``, ``preferred_supplier_id``,
  ``reorder_quantity``, ``reorder_lead_buffer_days``. A product must have
  BOTH the org switch on AND ``preferred_supplier_id`` set before the
  scheduler ever creates a draft PO for it.
* ``auto_reorder_runs`` — every invocation writes one row regardless of
  outcome, for the Settings → Auto-reorder run history and analytics.

Draft POs created by this pathway go through the existing
``purchase_orders`` table with ``status='DRAFT'``. No new PO columns are
added here — keeping auto-reorder output identical in shape to
manually-created POs means the approval UI, send flow, and audit log
already cover it.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b5d7f9a1c3e8"
down_revision = "f3a5c7d9e1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── organizations ───────────────────────────────────────────────────
    op.add_column(
        "organizations",
        sa.Column(
            "auto_reorder_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "auto_reorder_time",
            sa.Time(),
            server_default=sa.text("'06:00:00'"),
            nullable=False,
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "auto_reorder_days",
            sa.String(length=64),
            server_default=sa.text("'MON,WED,FRI'"),
            nullable=False,
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "auto_reorder_notify_email",
            sa.String(length=255),
            nullable=True,
        ),
    )

    # ── products ────────────────────────────────────────────────────────
    op.add_column(
        "products",
        sa.Column(
            "auto_reorder_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "preferred_supplier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_products_preferred_supplier_id",
        "products",
        ["preferred_supplier_id"],
    )
    op.add_column(
        "products",
        sa.Column("reorder_quantity", sa.Integer(), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column(
            "reorder_lead_buffer_days",
            sa.Integer(),
            server_default=sa.text("3"),
            nullable=False,
        ),
    )

    # ── auto_reorder_runs ───────────────────────────────────────────────
    op.create_table(
        "auto_reorder_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "triggered_by",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'scheduler'"),
        ),
        sa.Column(
            "run_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "products_checked",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "purchase_orders_created",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "products_skipped",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'completed'"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_auto_reorder_runs_org_id",
        "auto_reorder_runs",
        ["org_id"],
    )
    # Composite index for the "last 30 runs for this org" query used by
    # the run-history endpoint and the analytics KPI.
    op.create_index(
        "ix_auto_reorder_runs_org_run_at",
        "auto_reorder_runs",
        ["org_id", "run_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_auto_reorder_runs_org_run_at", table_name="auto_reorder_runs")
    op.drop_index("ix_auto_reorder_runs_org_id", table_name="auto_reorder_runs")
    op.drop_table("auto_reorder_runs")

    op.drop_column("products", "reorder_lead_buffer_days")
    op.drop_column("products", "reorder_quantity")
    op.drop_index("ix_products_preferred_supplier_id", table_name="products")
    op.drop_column("products", "preferred_supplier_id")
    op.drop_column("products", "auto_reorder_enabled")

    op.drop_column("organizations", "auto_reorder_notify_email")
    op.drop_column("organizations", "auto_reorder_days")
    op.drop_column("organizations", "auto_reorder_time")
    op.drop_column("organizations", "auto_reorder_enabled")
