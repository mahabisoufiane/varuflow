"""v90 — Purchase order notes (Item 89).

Threaded text notes attached to a purchase order. Lets procurement
staff log supplier calls, delivery-dispute context, back-order
promises, etc. next to the PO record. Authored by a member, can be
pinned (bubbled to the top of the PO sidebar), mentions extracted
for the activity feed.

Revision: b4c6d8e0f2a7
Revises:  a2b4c6d8e0f5 (v89 — invoice tags, Item 87)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b4c6d8e0f2a7"
down_revision = "a2b4c6d8e0f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_order_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "purchase_order_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # author_user_id is a bare UUID snapshot — auth users live in
        # Supabase, not this DB. Audit log keeps the mapping honest.
        sa.Column(
            "author_user_id", postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "is_pinned", sa.Boolean(),
            nullable=False, server_default=sa.false(),
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
        "ix_purchase_order_notes_org_id",
        "purchase_order_notes", ["org_id"],
    )
    # Hot-query index — the PO detail sidebar sorts pinned first
    # then newest-first, filtered by purchase_order_id. A composite
    # index over the exact sort keys lets Postgres stream results
    # without sorting.
    op.create_index(
        "ix_purchase_order_notes_po_pin_created",
        "purchase_order_notes",
        ["purchase_order_id", "is_pinned", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_purchase_order_notes_po_pin_created",
        table_name="purchase_order_notes",
    )
    op.drop_index(
        "ix_purchase_order_notes_org_id",
        table_name="purchase_order_notes",
    )
    op.drop_table("purchase_order_notes")
