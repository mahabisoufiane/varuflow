"""v85 — Product tags (Item 81).

Lightweight labels (name + hex color) owned by an organization that
can be applied to products many-to-many. Used for segmentation in
the product list ("seasonal", "bestseller", "slow mover"), for
filtering in POS and inventory views, and for driving bulk actions
later on.

Revision: c7d9e1f3a5b8
Revises:  b6c8d0e2f4a7 (v84 — product notes, Item 80)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c7d9e1f3a5b8"
down_revision = "b6c8d0e2f4a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=64), nullable=False),
        # Hex color string like "#2d6a4f". Stored as 7-char CHAR — the
        # service normalises to lower case and validates format.
        sa.Column("color", sa.String(length=7), nullable=False),
        sa.Column(
            "created_by_user_id", postgresql.UUID(as_uuid=True),
            nullable=False,
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
        "ix_product_tags_org_id", "product_tags", ["org_id"],
    )
    # Case-insensitive uniqueness per org so "Seasonal" and "seasonal"
    # collide at the DB level.
    op.create_index(
        "ux_product_tags_org_name_lower",
        "product_tags",
        ["org_id", sa.text("lower(name)")],
        unique=True,
    )

    op.create_table(
        "product_tag_assignments",
        sa.Column(
            "product_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tag_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_tags.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assigned_by_user_id", postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "assigned_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint(
            "product_id", "tag_id",
            name="pk_product_tag_assignments",
        ),
    )
    # Hot-query index — the PK covers "tags on product Y" scans, but
    # "products with tag X" and CASCADE cleanup on tag delete both
    # benefit from an explicit tag_id index.
    op.create_index(
        "ix_product_tag_assignments_tag_id",
        "product_tag_assignments", ["tag_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_product_tag_assignments_tag_id",
        table_name="product_tag_assignments",
    )
    op.drop_table("product_tag_assignments")
    op.drop_index(
        "ux_product_tags_org_name_lower", table_name="product_tags",
    )
    op.drop_index("ix_product_tags_org_id", table_name="product_tags")
    op.drop_table("product_tags")
