"""v87 — Warehouse tags (Item 84).

Lightweight labels (name + hex color) owned by an organization that
can be applied to warehouses many-to-many. Used for segmentation in
warehouse pickers and analytics ("cold-chain", "hazardous",
"satellite", "primary"), and for driving bulk ops later on.

Revision: e9f1a3b5c7d2
Revises:  d8e0f2a5b9c4 (v86 — warehouse notes, Item 83)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e9f1a3b5c7d2"
down_revision = "d8e0f2a5b9c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "warehouse_tags",
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
        "ix_warehouse_tags_org_id", "warehouse_tags", ["org_id"],
    )
    # Case-insensitive uniqueness per org so "Cold-chain" and
    # "cold-chain" collide at the DB level.
    op.create_index(
        "ux_warehouse_tags_org_name_lower",
        "warehouse_tags",
        ["org_id", sa.text("lower(name)")],
        unique=True,
    )

    op.create_table(
        "warehouse_tag_assignments",
        sa.Column(
            "warehouse_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tag_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("warehouse_tags.id", ondelete="CASCADE"),
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
            "warehouse_id", "tag_id",
            name="pk_warehouse_tag_assignments",
        ),
    )
    # Hot-query index — the PK covers "tags on warehouse Y" scans,
    # but "warehouses with tag X" and CASCADE cleanup on tag delete
    # both benefit from an explicit tag_id index.
    op.create_index(
        "ix_warehouse_tag_assignments_tag_id",
        "warehouse_tag_assignments", ["tag_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_warehouse_tag_assignments_tag_id",
        table_name="warehouse_tag_assignments",
    )
    op.drop_table("warehouse_tag_assignments")
    op.drop_index(
        "ux_warehouse_tags_org_name_lower", table_name="warehouse_tags",
    )
    op.drop_index("ix_warehouse_tags_org_id", table_name="warehouse_tags")
    op.drop_table("warehouse_tags")
