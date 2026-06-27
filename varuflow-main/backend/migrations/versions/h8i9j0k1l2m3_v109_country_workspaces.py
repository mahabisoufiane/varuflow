"""v109 — country workspaces (entity_type, parent_org_id, country_code on organizations)

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "h8i9j0k1l2m3"
down_revision = "g7h8i9j0k1l2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "entity_type",
            sa.String(20),
            server_default="standalone",
            nullable=False,
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "parent_org_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "organizations",
        sa.Column("country_code", sa.String(2), nullable=True),
    )
    op.create_index("ix_organizations_parent_org_id", "organizations", ["parent_org_id"])


def downgrade() -> None:
    op.drop_index("ix_organizations_parent_org_id", table_name="organizations")
    op.drop_column("organizations", "country_code")
    op.drop_column("organizations", "parent_org_id")
    op.drop_column("organizations", "entity_type")
