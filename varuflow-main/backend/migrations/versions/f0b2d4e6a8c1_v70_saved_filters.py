"""v70 — Saved filters (Item 61).

User-named filter presets for list pages (products, customers,
invoices, appointments). Each row is scoped to a specific
``entity_type`` and owner (``user_id``). Owners can opt-in to
``is_shared = true`` to make the preset visible to the whole org.

Why not just store JSON in a user-preferences blob: structure makes
list/delete/rename cheap and the org-wide visibility flag is a row
attribute — no need to re-serialise the whole blob on every toggle.

Revision: f0b2d4e6a8c1
Revises:  e9a1c3d5f7b0 (v69 — tags, Item 60)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f0b2d4e6a8c1"
down_revision = "e9a1c3d5f7b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_filters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # AuthUser UUID — references auth.users in Supabase, local
        # UUID otherwise. No FK: the Supabase side doesn't live in
        # this schema.
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        # entity_type ∈ {product, customer, invoice, appointment}
        sa.Column("entity_type", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        # Filter payload. Service-layer schema validates shape
        # (clauses + sort). Kept as JSONB so Postgres can search
        # within it later if we want to power "which filter depends
        # on this tag" queries.
        sa.Column(
            "definition",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "is_shared",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "org_id",
            "user_id",
            "entity_type",
            "name",
            name="uq_saved_filters_owner_entity_name",
        ),
    )
    op.create_index(
        "ix_saved_filters_org_entity",
        "saved_filters",
        ["org_id", "entity_type"],
    )
    op.create_index(
        "ix_saved_filters_shared",
        "saved_filters",
        ["org_id", "entity_type"],
        postgresql_where=sa.text("is_shared = true"),
    )


def downgrade() -> None:
    op.drop_index("ix_saved_filters_shared", table_name="saved_filters")
    op.drop_index("ix_saved_filters_org_entity", table_name="saved_filters")
    op.drop_table("saved_filters")
