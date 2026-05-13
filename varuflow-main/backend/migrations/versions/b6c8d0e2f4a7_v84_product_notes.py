"""v84 — Product notes (Item 80).

Threaded text notes attached to a product. Each note carries its
author and can be pinned (bubbled to the top of the product's
profile). Used by inventory staff to track quality-issue history,
storage quirks, supplier complaints, etc.

Revision: b6c8d0e2f4a7
Revises:  a5b7c9d1e3f6 (v83 — supplier contacts, Item 78)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b6c8d0e2f4a7"
down_revision = "a5b7c9d1e3f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
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
        "ix_product_notes_org_id", "product_notes", ["org_id"],
    )
    # Hot-query index — the product profile sidebar sorts pinned
    # first then newest first, filtered by product_id. A composite
    # index over the exact sort keys lets Postgres stream results
    # without a sort step.
    op.create_index(
        "ix_product_notes_product_pin_created",
        "product_notes",
        ["product_id", "is_pinned", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_product_notes_product_pin_created",
        table_name="product_notes",
    )
    op.drop_index(
        "ix_product_notes_org_id", table_name="product_notes",
    )
    op.drop_table("product_notes")
