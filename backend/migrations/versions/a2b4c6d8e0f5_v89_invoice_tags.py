"""v89 — Invoice tags (Item 87).

Lightweight labels (name + hex color) owned by an organization that
can be applied to invoices many-to-many. Used for segmentation in
invoice lists and analytics ("rush", "disputed", "recurring",
"wholesale"), and for driving bulk ops later on.

Revision: a2b4c6d8e0f5
Revises:  f0a2b4c6d8e3 (v88 — invoice notes, Item 86)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a2b4c6d8e0f5"
down_revision = "f0a2b4c6d8e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoice_tags",
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
        "ix_invoice_tags_org_id", "invoice_tags", ["org_id"],
    )
    # Case-insensitive uniqueness per org so "Rush" and "rush"
    # collide at the DB level.
    op.create_index(
        "ux_invoice_tags_org_name_lower",
        "invoice_tags",
        ["org_id", sa.text("lower(name)")],
        unique=True,
    )

    op.create_table(
        "invoice_tag_assignments",
        sa.Column(
            "invoice_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tag_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoice_tags.id", ondelete="CASCADE"),
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
            "invoice_id", "tag_id",
            name="pk_invoice_tag_assignments",
        ),
    )
    # Hot-query index — the PK covers "tags on invoice Y" scans,
    # but "invoices with tag X" and CASCADE cleanup on tag delete
    # both benefit from an explicit tag_id index.
    op.create_index(
        "ix_invoice_tag_assignments_tag_id",
        "invoice_tag_assignments", ["tag_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_invoice_tag_assignments_tag_id",
        table_name="invoice_tag_assignments",
    )
    op.drop_table("invoice_tag_assignments")
    op.drop_index(
        "ux_invoice_tags_org_name_lower", table_name="invoice_tags",
    )
    op.drop_index("ix_invoice_tags_org_id", table_name="invoice_tags")
    op.drop_table("invoice_tags")
