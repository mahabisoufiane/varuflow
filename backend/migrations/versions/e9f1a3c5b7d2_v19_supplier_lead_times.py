"""v19: supplier_lead_times table + supplier default/average lead days

Revision ID: e9f1a3c5b7d2
Revises: d8e0f2a4b6c9
Create Date: 2026-04-22

Tracks actual observed lead time per purchase order so we can detect
suppliers that run slower than their contracted default. A row is
inserted every time a PO transitions ``SENT -> RECEIVED``; the
``suppliers.average_lead_days`` column is a denormalised rolling mean
refreshed at capture time so dashboards and the AI engine can read
without a per-request aggregation.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e9f1a3c5b7d2"
down_revision = "d8e0f2a4b6c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Supplier columns — all optional, backfill is natural as POs get
    # received. ``default_lead_days`` is the supplier-promised number;
    # ``average_lead_days`` is what we actually observe.
    op.add_column(
        "suppliers",
        sa.Column("default_lead_days", sa.Integer(), nullable=True),
    )
    op.add_column(
        "suppliers",
        sa.Column("average_lead_days", sa.Numeric(5, 1), nullable=True),
    )
    op.add_column(
        "suppliers",
        sa.Column(
            "last_lead_measured_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_table(
        "supplier_lead_times",
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
            index=True,
        ),
        sa.Column(
            "supplier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "purchase_order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        # Stored column (not generated) because SQLAlchemy/Alembic
        # generated columns require a dialect-specific dance; computing
        # at insert is simpler and equally correct.
        sa.Column("lead_days", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # One lead-time record per PO; re-capturing should be an upsert
        # so repeated receives (or job retries) don't double-count.
        sa.UniqueConstraint(
            "purchase_order_id", name="uq_supplier_lead_times_po",
        ),
    )
    op.create_index(
        "ix_supplier_lead_times_supplier_received",
        "supplier_lead_times",
        ["supplier_id", "received_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_supplier_lead_times_supplier_received",
        table_name="supplier_lead_times",
    )
    op.drop_table("supplier_lead_times")
    op.drop_column("suppliers", "last_lead_measured_at")
    op.drop_column("suppliers", "average_lead_days")
    op.drop_column("suppliers", "default_lead_days")
