"""mfg3 — qc_checklists and qc_inspections

Revision ID: s8m9n0o1p2q3
Revises:     r7m8n9o0p1q2
Create Date: 2026-04-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "s8m9n0o1p2q3"
down_revision = "r7m8n9o0p1q2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "qc_checklists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("applies_to", sa.String(20), nullable=False),
        sa.Column("items", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_qc_checklists_org_id", "qc_checklists", ["org_id"])

    op.create_table(
        "qc_inspections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("checklist_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("qc_checklists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("work_order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("results", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("inspector_name", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("inspected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_qc_inspections_org_id", "qc_inspections", ["org_id"])
    op.create_index("ix_qc_inspections_checklist_id", "qc_inspections", ["checklist_id"])
    op.create_index("ix_qc_inspections_work_order_id", "qc_inspections", ["work_order_id"])
    op.create_index("ix_qc_inspections_batch_id", "qc_inspections", ["batch_id"])


def downgrade() -> None:
    op.drop_table("qc_inspections")
    op.drop_table("qc_checklists")
