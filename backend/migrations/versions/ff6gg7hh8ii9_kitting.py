"""kitting: create kit_definitions, kit_components, kit_assemblies tables

Revision ID: ff6gg7hh8ii9
Revises: ee5ff6gg7hh8
Create Date: 2026-05-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "ff6gg7hh8ii9"
down_revision = "ee5ff6gg7hh8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kit_definitions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("custom_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_kit_definitions_org_id", "kit_definitions", ["org_id"])
    op.create_index("ix_kit_definitions_product_id", "kit_definitions", ["product_id"])

    op.create_table(
        "kit_components",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("kit_id", UUID(as_uuid=True), sa.ForeignKey("kit_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("component_product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
    )
    op.create_index("ix_kit_components_kit_id", "kit_components", ["kit_id"])
    op.create_index("ix_kit_components_component_product_id", "kit_components", ["component_product_id"])

    op.create_table(
        "kit_assemblies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kit_id", UUID(as_uuid=True), sa.ForeignKey("kit_definitions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("direction", sa.String(12), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("assembled_by_staff_id", UUID(as_uuid=True), nullable=True),
        sa.Column("assembled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_kit_assemblies_org_id", "kit_assemblies", ["org_id"])
    op.create_index("ix_kit_assemblies_kit_id", "kit_assemblies", ["kit_id"])


def downgrade() -> None:
    op.drop_table("kit_assemblies")
    op.drop_table("kit_components")
    op.drop_table("kit_definitions")
