"""v108 — org branding table (white-label)

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "g7h8i9j0k1l2"
down_revision = "f6g7h8i9j0k1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "org_branding",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("app_name", sa.String(100), nullable=True),
        sa.Column("logo_url", sa.String(2000), nullable=True),
        sa.Column("favicon_url", sa.String(2000), nullable=True),
        sa.Column("primary_color", sa.String(7), nullable=True),
        sa.Column("accent_color", sa.String(7), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_org_branding_org_id", "org_branding", ["org_id"], unique=True)


def downgrade() -> None:
    op.drop_table("org_branding")
