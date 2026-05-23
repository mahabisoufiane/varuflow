"""v79 — Customer tags (Item 73).

Lightweight labels (name + hex color) owned by an organization that
can be applied to customers many-to-many. Used for segmentation,
filtering in the customer list, and driving bulk actions (bulk
statements / bulk email campaigns later on).

Revision: c1d3e5f7a9b2
Revises:  b9c1d3e5f7a8 (v78 — customer notes, Item 71)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c1d3e5f7a9b2"
down_revision = "b9c1d3e5f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_tags",
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
        "ix_customer_tags_org_id", "customer_tags", ["org_id"],
    )
    # Case-insensitive uniqueness per org so "VIP" and "vip" collide.
    op.create_index(
        "ux_customer_tags_org_name_lower",
        "customer_tags",
        ["org_id", sa.text("lower(name)")],
        unique=True,
    )

    op.create_table(
        "customer_tag_assignments",
        sa.Column(
            "customer_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tag_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_tags.id", ondelete="CASCADE"),
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
            "customer_id", "tag_id",
            name="pk_customer_tag_assignments",
        ),
    )
    # Hot-query index: "list customers with tag X" and
    # "list tags on customer Y" are both served from the PK, but
    # we also want fast tag-drop on customer delete and vice versa.
    op.create_index(
        "ix_customer_tag_assignments_tag_id",
        "customer_tag_assignments", ["tag_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_customer_tag_assignments_tag_id",
        table_name="customer_tag_assignments",
    )
    op.drop_table("customer_tag_assignments")
    op.drop_index(
        "ux_customer_tags_org_name_lower", table_name="customer_tags",
    )
    op.drop_index("ix_customer_tags_org_id", table_name="customer_tags")
    op.drop_table("customer_tags")
