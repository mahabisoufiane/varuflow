"""v86 — Warehouse notes (Item 83).

Threaded text notes attached to a warehouse. Each note carries its
author and can be pinned (bubbled to the top of the warehouse's
profile). Used by operations staff to track access quirks, safety
incidents, cold-chain outages, etc.

Revision: d8e0f2a5b9c4
Revises:  c7d9e1f3a5b8 (v85 — product tags, Item 81)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d8e0f2a5b9c4"
down_revision = "c7d9e1f3a5b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "warehouse_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "warehouse_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # author_user_id is a bare UUID snapshot — the auth users
        # table lives outside this DB (Supabase). Audit log keeps the
        # mapping honest.
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
        "ix_warehouse_notes_org_id", "warehouse_notes", ["org_id"],
    )
    # Hot-query index — the warehouse profile sidebar sorts pinned
    # first then newest first, filtered by warehouse_id. A composite
    # index over the exact sort keys lets Postgres stream results
    # without a sort step.
    op.create_index(
        "ix_warehouse_notes_wh_pin_created",
        "warehouse_notes",
        ["warehouse_id", "is_pinned", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_warehouse_notes_wh_pin_created",
        table_name="warehouse_notes",
    )
    op.drop_index(
        "ix_warehouse_notes_org_id", table_name="warehouse_notes",
    )
    op.drop_table("warehouse_notes")
