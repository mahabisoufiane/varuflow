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
    # entity_type + parent_org_id (and the ix_organizations_parent_org_id index)
    # are already added on a parallel branch by a4u5v6w7x8y9 (multi_entity_
    # franchise) with identical definitions. Re-adding them here duplicated the
    # columns on a fresh `alembic upgrade head` (DuplicateColumnError). This
    # migration now contributes only country_code.
    op.add_column(
        "organizations",
        sa.Column("country_code", sa.String(2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organizations", "country_code")
