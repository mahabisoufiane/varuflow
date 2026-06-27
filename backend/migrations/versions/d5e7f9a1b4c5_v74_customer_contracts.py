"""v74 — Customer contracts (Item 66).

Tracks formal agreements with customers: service contracts,
retainers, subscriptions-as-documents. Distinct from recurring
invoices (Item 26) which live at the billing layer — contracts are
the legal document side.

Revision: d5e7f9a1b4c5
Revises:  c4d6e8f0a2b3 (v73 — pos quick buttons, Item 65)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d5e7f9a1b4c5"
down_revision = "c4d6e8f0a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    contract_status = sa.Enum(
        "DRAFT", "ACTIVE", "EXPIRED", "TERMINATED",
        name="contract_status",
    )
    contract_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "customer_contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("status", contract_status, nullable=False, server_default="DRAFT"),
        sa.Column("start_date", sa.Date(), nullable=False),
        # Open-ended contracts (e.g. retainers) have NULL end_date.
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column(
            "value_amount", sa.Numeric(14, 2), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="SEK"),
        # Operator pastes legal text here — rendered as plain text / preformatted.
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column(
            "auto_renew_months", sa.Integer(), nullable=True,
        ),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("termination_reason", sa.String(length=500), nullable=True),
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
        "ix_customer_contracts_org", "customer_contracts", ["org_id"],
    )
    op.create_index(
        "ix_customer_contracts_customer", "customer_contracts", ["customer_id"],
    )
    # Range-end lookup for the expiry sweep.
    op.create_index(
        "ix_customer_contracts_end_date",
        "customer_contracts",
        ["org_id", "end_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_customer_contracts_end_date", table_name="customer_contracts")
    op.drop_index("ix_customer_contracts_customer", table_name="customer_contracts")
    op.drop_index("ix_customer_contracts_org", table_name="customer_contracts")
    op.drop_table("customer_contracts")
    sa.Enum(name="contract_status").drop(op.get_bind(), checkfirst=True)
