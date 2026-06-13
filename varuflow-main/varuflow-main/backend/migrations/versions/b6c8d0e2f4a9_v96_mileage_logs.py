"""v96 — Mileage logs (Item 98).

A `mileage_log` records a single trip (date, distance_km,
rate_per_km, denormalised amount, currency, optional
origin/destination/purpose/category). Logs can be promoted to an
`Expense` via the router's ``/convert`` endpoint, after which
``expense_id`` + ``converted_at`` are set to make the link
explicit.

Revision: b6c8d0e2f4a9
Revises:  a4b6c8d0e2f7 (v95 — recurring expenses, Item 97)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b6c8d0e2f4a9"
down_revision = "a4b6c8d0e2f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mileage_logs",
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
        sa.Column("trip_date", sa.Date(), nullable=False),
        sa.Column("distance_km", sa.Numeric(10, 2), nullable=False),
        # 4 decimals: most tax authorities publish per-km rates with
        # up to 4 decimals (e.g. SE Skatteverket = 25.0000).
        sa.Column("rate_per_km", sa.Numeric(10, 4), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "currency", sa.String(length=3), nullable=False,
            server_default="SEK",
        ),
        sa.Column(
            "category_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expense_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("origin", sa.String(length=200), nullable=True),
        sa.Column("destination", sa.String(length=200), nullable=True),
        sa.Column("purpose", sa.String(length=255), nullable=True),
        sa.Column("vehicle", sa.String(length=40), nullable=True),
        sa.Column(
            "expense_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expenses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "converted_at", sa.DateTime(timezone=True), nullable=True,
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
        "ix_mileage_logs_org_id", "mileage_logs", ["org_id"],
    )
    # Hot range query: "trips for org X in date range Y..Z".
    op.create_index(
        "ix_mileage_logs_org_trip_date",
        "mileage_logs", ["org_id", "trip_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_mileage_logs_org_trip_date", table_name="mileage_logs")
    op.drop_index("ix_mileage_logs_org_id", table_name="mileage_logs")
    op.drop_table("mileage_logs")
