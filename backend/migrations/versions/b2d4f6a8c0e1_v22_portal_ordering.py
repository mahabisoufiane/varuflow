"""v22: self-service portal ordering — toggles + RESERVED stock movement

Revision ID: b2d4f6a8c0e1
Revises: a1c3e5f7b9d4
Create Date: 2026-04-22

Adds the infrastructure needed for B2B customers to place orders from
the portal:

* ``customers.portal_ordering_enabled`` — per-customer opt-in. Defaults
  to ``FALSE`` so rolling out this feature does not silently expose the
  ordering UI to every existing portal user.
* ``organizations.orders_notification_email`` — address that receives the
  internal "new portal order" email. ``NULL`` disables the internal
  notification (customer still gets their confirmation).
* ``RESERVED`` value on the ``stock_movement_type`` enum — used by the
  portal order endpoint to decrement on-hand visibility when a customer
  reserves goods against a draft invoice.
"""
from alembic import op
import sqlalchemy as sa

revision = "b2d4f6a8c0e1"
down_revision = "a1c3e5f7b9d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column(
            "portal_ordering_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "orders_notification_email",
            sa.String(length=255),
            nullable=True,
        ),
    )

    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block, so
    # break out of the Alembic-managed transaction for this one statement.
    # IF NOT EXISTS makes the migration idempotent on re-run.
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE stock_movement_type ADD VALUE IF NOT EXISTS 'RESERVED'"
        )


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum value in place. If a rollback
    # is ever needed we rebuild the type. The column drops below are
    # straightforward.
    op.drop_column("organizations", "orders_notification_email")
    op.drop_column("customers", "portal_ordering_enabled")
    # Intentionally leaves the enum value in place — removing it requires
    # rewriting every stock_movements row and recreating the enum, which
    # is far more disruptive than an unused value.
