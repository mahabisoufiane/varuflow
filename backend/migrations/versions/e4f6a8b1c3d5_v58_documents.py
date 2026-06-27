"""v58 — document storage (Item 44).

Single new table ``documents`` — one row per uploaded business
document (contract, certificate, compliance record, etc.).

* ``category`` is a lightweight enum at the pydantic layer rather
  than a PostgreSQL ENUM so a new SMB-specific category can be
  added without a migration. The router validates.
* ``tags`` is a ``text[]`` array so search-by-tag is an index-
  friendly ``@>`` containment query rather than a substring match.
* ``expires_at`` is an indexed timestamp so the nightly expiry
  sweep lands on a hot small-result query.
* ``linked_type`` + ``linked_id`` form a polymorphic pointer to
  an optional supplier / customer / product. Polymorphic FKs are
  not enforced at the schema level by design — the UI surfaces the
  link only if the target still exists.

Spec suggested v50; v50 is already occupied by
``b8c9d0e1f2a3_v50_multi_currency.py``. Landed at v58 —
chains from v57 expenses.

Revision: e4f6a8b1c3d5
Revises:  d3e5f7a9b2c4 (v57 — expenses, Item 43)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e4f6a8b1c3d5"
down_revision = "d3e5f7a9b2c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=300), nullable=False),
        # Free-form category string, validated at router layer against
        # the service-layer allow-list. Keeping it open-ended so a
        # tenant can add categories without a migration.
        sa.Column(
            "category",
            sa.String(length=60), nullable=False, server_default="other",
        ),
        # Object-store URL. The tenant uploads via a presigned URL
        # on the client and we only persist the final location here
        # so the API layer stays network-free at write time.
        sa.Column("file_url", sa.String(length=2048), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String(length=60)),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        # Uploader reference. Nullable so a user deletion doesn't
        # break the document history (audit-safe).
        sa.Column(
            "uploaded_by",
            postgresql.UUID(as_uuid=True), nullable=True,
        ),
        # Polymorphic link to an owning entity — supplier / customer /
        # product. Kept nullable so unlinked documents (e.g. a general
        # compliance certificate) are valid.
        sa.Column(
            "linked_type",
            sa.String(length=40), nullable=True,
        ),
        sa.Column(
            "linked_id",
            postgresql.UUID(as_uuid=True), nullable=True,
        ),
        # Optional expiry for contracts / certificates. The scheduler
        # sweeps this column nightly (in a follow-up) to ping owners
        # about imminent expirations.
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True), nullable=True,
        ),
        # Team sharing — simple bool for v1. ``is_shared=True`` makes
        # the document visible to every member of the org; False
        # restricts read to uploader + owners/admins.
        sa.Column(
            "is_shared",
            sa.Boolean, nullable=False, server_default=sa.text("true"),
        ),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_documents_org",
        "documents",
        ["org_id"],
    )
    # Category filter on the list page — covered composite keeps the
    # common case (filter by category for an org) to a single index
    # scan even at millions of rows.
    op.create_index(
        "ix_documents_org_category",
        "documents",
        ["org_id", "category"],
    )
    # Expiry sweep — partial index scoped to non-null expiry so rows
    # without an expiry date don't bloat the index.
    op.create_index(
        "ix_documents_expires",
        "documents",
        ["expires_at"],
        postgresql_where=sa.text("expires_at IS NOT NULL"),
    )
    # GIN index on tags[] for ``WHERE tags @> ARRAY['foo']`` lookups.
    op.create_index(
        "ix_documents_tags_gin",
        "documents",
        ["tags"],
        postgresql_using="gin",
    )
    # Polymorphic link lookup — "show me all docs attached to this
    # supplier/customer/product".
    op.create_index(
        "ix_documents_linked",
        "documents",
        ["org_id", "linked_type", "linked_id"],
        postgresql_where=sa.text("linked_type IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_documents_linked", table_name="documents")
    op.drop_index("ix_documents_tags_gin", table_name="documents")
    op.drop_index("ix_documents_expires", table_name="documents")
    op.drop_index("ix_documents_org_category", table_name="documents")
    op.drop_index("ix_documents_org", table_name="documents")
    op.drop_table("documents")
