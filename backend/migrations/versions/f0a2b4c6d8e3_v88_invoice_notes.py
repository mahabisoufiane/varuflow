"""v88 — Invoice notes (Item 86).

Threaded text notes attached to an invoice. Lets billing / AR staff
log collection calls, dispute context, payment promises, etc. next
to the invoice record. Authored by a member, can be pinned (bubbled
to the top of the invoice sidebar), mentions extracted for the
activity feed.

Revision: f0a2b4c6d8e3
Revises:  e9f1a3b5c7d2 (v87 — warehouse tags, Item 84)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f0a2b4c6d8e3"
down_revision = "e9f1a3b5c7d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoice_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "invoice_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
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
        "ix_invoice_notes_org_id", "invoice_notes", ["org_id"],
    )
    # Hot-query index — the invoice detail sidebar sorts pinned first
    # then newest-first, filtered by invoice_id. A composite index over
    # the exact sort keys lets Postgres stream results without sorting.
    op.create_index(
        "ix_invoice_notes_inv_pin_created",
        "invoice_notes",
        ["invoice_id", "is_pinned", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_invoice_notes_inv_pin_created",
        table_name="invoice_notes",
    )
    op.drop_index(
        "ix_invoice_notes_org_id", table_name="invoice_notes",
    )
    op.drop_table("invoice_notes")
