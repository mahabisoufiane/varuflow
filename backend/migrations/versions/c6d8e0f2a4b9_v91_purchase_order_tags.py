"""v91 — Purchase order tags (Item 90).

Lightweight labels (name + hex color) owned by an organization that
can be applied to purchase orders many-to-many. Used for
segmentation in PO lists and analytics ("rush", "urgent",
"backorder", "import"), and for driving bulk ops later on.

Revision: c6d8e0f2a4b9
Revises:  b4c6d8e0f2a7 (v90 — purchase order notes, Item 89)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c6d8e0f2a4b9"
down_revision = "b4c6d8e0f2a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_order_tags",
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
        "ix_purchase_order_tags_org_id",
        "purchase_order_tags", ["org_id"],
    )
    # Case-insensitive uniqueness per org so "Rush" and "rush"
    # collide at the DB level.
    op.create_index(
        "ux_purchase_order_tags_org_name_lower",
        "purchase_order_tags",
        ["org_id", sa.text("lower(name)")],
        unique=True,
    )

    op.create_table(
        "purchase_order_tag_assignments",
        sa.Column(
            "purchase_order_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tag_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("purchase_order_tags.id", ondelete="CASCADE"),
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
            "purchase_order_id", "tag_id",
            name="pk_purchase_order_tag_assignments",
        ),
    )
    # Hot-query index — the PK covers "tags on PO Y" scans, but
    # "POs with tag X" and CASCADE cleanup on tag delete both
    # benefit from an explicit tag_id index.
    op.create_index(
        "ix_purchase_order_tag_assignments_tag_id",
        "purchase_order_tag_assignments", ["tag_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_purchase_order_tag_assignments_tag_id",
        table_name="purchase_order_tag_assignments",
    )
    op.drop_table("purchase_order_tag_assignments")
    op.drop_index(
        "ux_purchase_order_tags_org_name_lower",
        table_name="purchase_order_tags",
    )
    op.drop_index(
        "ix_purchase_order_tags_org_id",
        table_name="purchase_order_tags",
    )
    op.drop_table("purchase_order_tags")
