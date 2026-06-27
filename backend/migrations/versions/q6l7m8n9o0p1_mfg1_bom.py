"""mfg1 — bom_headers and bom_lines

Revision ID: q6l7m8n9o0p1
Revises:     p5k6l7m8n9o0
Create Date: 2026-04-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "q6l7m8n9o0p1"
down_revision = "p5k6l7m8n9o0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bom_headers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("is_kit", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_id", "product_id", name="uq_bom_headers_org_product"),
    )
    op.create_index("ix_bom_headers_org_id", "bom_headers", ["org_id"])
    op.create_index("ix_bom_headers_product_id", "bom_headers", ["product_id"])

    op.create_table(
        "bom_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bom_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("bom_headers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("component_product_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False, server_default="st"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_bom_lines_bom_id", "bom_lines", ["bom_id"])
    op.create_index("ix_bom_lines_component_product_id", "bom_lines", ["component_product_id"])


def downgrade() -> None:
    op.drop_table("bom_lines")
    op.drop_table("bom_headers")
