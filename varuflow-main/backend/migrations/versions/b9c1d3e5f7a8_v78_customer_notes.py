"""v78 — Customer notes (Item 71).

Threaded text notes attached to a customer. Each note carries its
author and can be pinned (bubbled to the top of the customer's
profile). Used by account managers for call summaries, delivery
preferences, invoice follow-up history, etc.

Revision: b9c1d3e5f7a8
Revises:  a8b0c2d4e6f9 (v77 — credit notes, Item 70)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b9c1d3e5f7a8"
down_revision = "a8b0c2d4e6f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # author_user_id is a bare UUID — the auth users table lives
        # outside this DB (Supabase). We snapshot the id so deleting
        # a user doesn't orphan the history; audit log keeps the
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
        "ix_customer_notes_org_id", "customer_notes", ["org_id"],
    )
    op.create_index(
        "ix_customer_notes_customer_id",
        "customer_notes", ["customer_id"],
    )
    # Composite index for the hot query: "notes for this customer,
    # pinned first, newest first".
    op.create_index(
        "ix_customer_notes_customer_pinned_created",
        "customer_notes",
        ["customer_id", "is_pinned", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_customer_notes_customer_pinned_created",
        table_name="customer_notes",
    )
    op.drop_index(
        "ix_customer_notes_customer_id", table_name="customer_notes",
    )
    op.drop_index(
        "ix_customer_notes_org_id", table_name="customer_notes",
    )
    op.drop_table("customer_notes")
