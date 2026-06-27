"""v50 — multi-currency support (Item 34).

Creates ``exchange_rates`` and adds currency columns to transaction
tables + ``base_currency`` on organizations.

Revision: b8c9d0e1f2a3
Revises:  a7b8c9d0e1f2 (v49 — gift cards & bundles)

Design note
-----------
We deliberately DO NOT rename ``invoices.total_sek``. The column
becomes "total in the invoice's currency" regardless of the
historical name. Renaming would break every existing analytics
query and Fortnox export codepath; the new ``currency`` +
``exchange_rate`` columns carry the semantic instead.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Exchange rate snapshots.
    op.create_table(
        "exchange_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("target_currency", sa.String(3), nullable=False),
        sa.Column("rate", sa.Numeric(18, 8), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "base_currency", "target_currency", "fetched_at",
            name="uq_exchange_rates_base_target_fetched",
        ),
    )
    op.create_index(
        "ix_exchange_rates_base_target",
        "exchange_rates",
        ["base_currency", "target_currency", "fetched_at"],
    )

    # Organizations get a base currency.
    op.add_column(
        "organizations",
        sa.Column(
            "base_currency",
            sa.String(3),
            server_default="SEK",
            nullable=False,
        ),
    )

    # Invoices, payments, pos_sales get currency + exchange_rate.
    # ``exchange_rate`` stores "rate from transaction currency → org
    # base currency" at the moment the row was written, so analytics
    # can normalise historical rows even after live rates have drifted.
    for table in ("invoices", "payments", "pos_sales"):
        op.add_column(
            table,
            sa.Column(
                "currency",
                sa.String(3),
                server_default="SEK",
                nullable=False,
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "exchange_rate",
                sa.Numeric(18, 8),
                server_default="1",
                nullable=False,
            ),
        )


def downgrade() -> None:
    for table in ("pos_sales", "payments", "invoices"):
        op.drop_column(table, "exchange_rate")
        op.drop_column(table, "currency")
    op.drop_column("organizations", "base_currency")
    op.drop_index("ix_exchange_rates_base_target", table_name="exchange_rates")
    op.drop_table("exchange_rates")
