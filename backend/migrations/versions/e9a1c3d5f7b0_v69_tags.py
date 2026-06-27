"""v69 — Tag manager for products, customers and invoices (Item 60).

Operators need lightweight labels to segment records without
spinning up a custom field. Two tables:

* ``tags`` — per-org catalogue of available labels. Unique by
  ``(org_id, slug)``. Slug is the canonical, URL-safe form of the
  human-facing ``name``.
* ``tag_assignments`` — many-to-many link between a tag and a
  target row (product / customer / invoice). Unique on
  ``(tag_id, entity_type, entity_id)``.

Complements v68 custom fields (Item 59) — fields hold typed data,
tags hold membership flags. ``entity_type`` is kept as a small string
(same set as custom fields: ``product``, ``customer``, ``invoice``).

Revision: e9a1c3d5f7b0
Revises:  d8f0b2c4e6a9 (v68 — custom fields, Item 59)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e9a1c3d5f7b0"
down_revision = "d8f0b2c4e6a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        # 7-char hex colour e.g. #1E90FF — nullable so the UI can
        # auto-assign from a palette for tags created in bulk.
        sa.Column("color", sa.String(length=7), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("org_id", "slug", name="uq_tags_org_slug"),
    )
    op.create_index("ix_tags_org", "tags", ["org_id"])

    op.create_table(
        "tag_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tag_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=16), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "tag_id",
            "entity_type",
            "entity_id",
            name="uq_tag_assignments_tag_entity",
        ),
    )
    op.create_index(
        "ix_tag_assignments_entity",
        "tag_assignments",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "ix_tag_assignments_org_tag",
        "tag_assignments",
        ["org_id", "tag_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tag_assignments_org_tag", table_name="tag_assignments"
    )
    op.drop_index(
        "ix_tag_assignments_entity", table_name="tag_assignments"
    )
    op.drop_table("tag_assignments")
    op.drop_index("ix_tags_org", table_name="tags")
    op.drop_table("tags")
