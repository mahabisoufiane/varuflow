"""v65 — Product back-in-stock waitlist (Item 56).

One row per customer-interest-in-a-product. Customers (or staff on
their behalf) sign up to be notified when a stockout'd product has
stock again. The scheduler sweeps at the next Item 56+1 iteration;
for now the table and read/write endpoints are shipped so signups can
accrue.

Key choices:

* ``email`` is stored in plaintext (waitlist signup is inherently
  opt-in contact). Full GDPR semantics piggy-back on the existing
  ``/api/gdpr/*`` export/anonymise routes: a customer can ask for
  their row to be deleted.
* ``(org_id, product_id, email)`` unique — idempotent signup: a
  second POST for the same trio returns the existing row with a 200
  (vs 409) so the client can stay dumb.
* ``notified_at`` left NULL until the back-in-stock email goes out.
  Makes "who still needs a nudge" a trivial WHERE clause.

Revision: a5c7e9b1d3f6
Revises:  f4a6b8c0d2e7 (v64 — invoice installments, Item 54)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a5c7e9b1d3f6"
down_revision = "f4a6b8c0d2e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_waitlist_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("locale", sa.String(length=8), nullable=True),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "org_id",
            "product_id",
            "email",
            name="uq_product_waitlist_org_product_email",
        ),
    )
    op.create_index(
        "ix_product_waitlist_org_product",
        "product_waitlist_entries",
        ["org_id", "product_id"],
    )
    op.create_index(
        "ix_product_waitlist_pending",
        "product_waitlist_entries",
        ["product_id"],
        postgresql_where=sa.text("notified_at IS NULL AND cancelled_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_product_waitlist_pending", table_name="product_waitlist_entries"
    )
    op.drop_index(
        "ix_product_waitlist_org_product", table_name="product_waitlist_entries"
    )
    op.drop_table("product_waitlist_entries")
