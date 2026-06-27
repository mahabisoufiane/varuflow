"""v81 — Supplier notes (Item 76).

Threaded text notes attached to a supplier. Each note carries its
author and can be pinned (bubbled to the top of the supplier's
profile). Used by purchasing staff to track call summaries,
quality-issue history, lead-time quirks, etc.

Revision: e3f5a7b9c0d4
Revises:  d2e4f6a8b0c3 (v80 — customer contacts, Item 74)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e3f5a7b9c0d4"
down_revision = "d2e4f6a8b0c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id", ondelete="CASCADE"),
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
        "ix_supplier_notes_org_id", "supplier_notes", ["org_id"],
    )
    # Hot-query index — the supplier profile sidebar sorts pinned
    # first then newest first, filtered by supplier_id. A composite
    # index over the exact sort keys lets Postgres stream results
    # without a sort step.
    op.create_index(
        "ix_supplier_notes_supplier_pin_created",
        "supplier_notes",
        ["supplier_id", "is_pinned", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_supplier_notes_supplier_pin_created",
        table_name="supplier_notes",
    )
    op.drop_index(
        "ix_supplier_notes_org_id", table_name="supplier_notes",
    )
    op.drop_table("supplier_notes")
