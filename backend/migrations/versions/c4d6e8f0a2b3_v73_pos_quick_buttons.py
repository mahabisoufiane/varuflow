"""v73 — POS quick-sale buttons (Item 65).

Operators configure a small grid of "quick buttons" at the POS —
each button shortcut-adds a single product at a fixed quantity. The
button order is operator-controlled, so we store an explicit
``position`` column rather than relying on insertion order.

Revision: c4d6e8f0a2b3
Revises:  b3c5d7e9f1a4 (v72 — campaign blocks, Item 63)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c4d6e8f0a2b3"
down_revision = "b3c5d7e9f1a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pos_quick_buttons",
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
        sa.Column("label", sa.String(length=40), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=True),
        sa.Column(
            "quantity",
            sa.Numeric(10, 3),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # One button per (org, position). Operator reorders by swapping
        # positions inside a transaction.
        sa.UniqueConstraint(
            "org_id", "position", name="uq_pos_quick_buttons_org_position"
        ),
        # Same product can appear twice with different labels (e.g.
        # a coffee button and a "latte" button pointing to the same
        # SKU) so no unique on (org, product).
    )
    op.create_index(
        "ix_pos_quick_buttons_org", "pos_quick_buttons", ["org_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pos_quick_buttons_org", table_name="pos_quick_buttons"
    )
    op.drop_table("pos_quick_buttons")
