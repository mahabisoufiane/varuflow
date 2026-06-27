"""v51 — customer loyalty program (Item 35).

Introduces a points-based loyalty ledger with three tables:

* ``loyalty_programs`` — per-org configuration (one active row per org
  in practice, but the schema permits history / experimentation).
* ``loyalty_accounts`` — per-customer points balance, lifetime total
  and tier cache (Bronze/Silver/Gold/Platinum).
* ``loyalty_transactions`` — the ledger. Every earn/redeem/expire/adjust
  produces one row so balances are auditable and reversible.

Note on coexistence with the partial stub shipped in Item 31:
``appointments.loyalty_points_awarded`` is **kept** as an idempotency
guard — it tracks whether an appointment has already fed the ledger,
so the booking hook never double-credits.

Revision: c9d0e1f2a3b4
Revises:  b8c9d0e1f2a3 (v50 — multi-currency, Item 34)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Program configuration.
    op.create_table(
        "loyalty_programs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False, server_default="Loyalty"),
        sa.Column(
            "points_per_currency_unit",
            sa.Numeric(12, 4),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "redemption_rate",
            sa.Numeric(12, 6),
            nullable=False,
            server_default="0.01",
        ),
        sa.Column("expiry_days", sa.Integer, nullable=False, server_default="365"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_loyalty_programs_org_active",
        "loyalty_programs",
        ["org_id", "is_active"],
    )

    # Customer accounts.
    op.create_table(
        "loyalty_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("points_balance", sa.Integer, nullable=False, server_default="0"),
        sa.Column("lifetime_points", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tier", sa.String(32), nullable=False, server_default="bronze"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("org_id", "customer_id", name="uq_loyalty_accounts_org_customer"),
    )

    # Ledger.
    op.create_table(
        "loyalty_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("loyalty_accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # Signed integer: positive=credit, negative=debit.
        sa.Column("points", sa.Integer, nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=True),
        sa.Column("source_id", sa.String(128), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_loyalty_transactions_account_created",
        "loyalty_transactions",
        ["account_id", "created_at"],
    )
    op.create_index(
        "ix_loyalty_transactions_expiry",
        "loyalty_transactions",
        ["expires_at"],
        postgresql_where=sa.text("expires_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_loyalty_transactions_expiry", table_name="loyalty_transactions")
    op.drop_index("ix_loyalty_transactions_account_created", table_name="loyalty_transactions")
    op.drop_table("loyalty_transactions")
    op.drop_table("loyalty_accounts")
    op.drop_index("ix_loyalty_programs_org_active", table_name="loyalty_programs")
    op.drop_table("loyalty_programs")
