"""v39: recurring invoice auto-send + customer Peppol fields (Item 17)

Revision ID: c7e9a2b4d6f1
Revises: b5d7f9a1c3e8
Create Date: 2026-04-23

Adds the columns backing the recurring-invoice auto-send workflow:

* ``recurring_invoices.auto_send`` (bool, default false) — off by default
  so every pre-existing schedule keeps producing DRAFT invoices for
  manual review. Flip it on explicitly per schedule.
* ``recurring_invoices.auto_send_method`` (varchar, default "email") —
  comma-separated channels. Accepts "email", "peppol", or both. String
  rather than enum so adding new channels (sms, whatsapp — see Item 18)
  doesn't require another migration.
* ``customers.peppol_id`` (varchar, nullable) — the Peppol Participant
  Identifier (scheme:id) used as Peppol routing address.
* ``customers.peppol_enabled`` (bool, default false) — opt-in switch.
  Peppol auto-send only fires when BOTH this is true AND a peppol_id
  is set, which keeps the upgrade side-effect free.
"""
from alembic import op
import sqlalchemy as sa


revision = "c7e9a2b4d6f1"
down_revision = "b5d7f9a1c3e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recurring_invoices",
        sa.Column(
            "auto_send",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "recurring_invoices",
        sa.Column(
            "auto_send_method",
            sa.String(length=32),
            server_default=sa.text("'email'"),
            nullable=False,
        ),
    )

    op.add_column(
        "customers",
        sa.Column("peppol_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column(
            "peppol_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("customers", "peppol_enabled")
    op.drop_column("customers", "peppol_id")
    op.drop_column("recurring_invoices", "auto_send_method")
    op.drop_column("recurring_invoices", "auto_send")
