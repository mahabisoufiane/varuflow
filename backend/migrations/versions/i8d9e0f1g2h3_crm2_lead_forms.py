"""crm2 — lead_forms and lead_form_submissions tables

Revision ID: i8d9e0f1g2h3
Revises:     h7c8d9e0f1g2
Create Date: 2026-04-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "i8d9e0f1g2h3"
down_revision = "h7c8d9e0f1g2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lead_forms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(80), unique=True, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("fields", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("redirect_url", sa.Text, nullable=True),
        sa.Column("notify_email", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_lead_forms_org_id", "lead_forms", ["org_id"])
    op.create_index("ix_lead_forms_slug", "lead_forms", ["slug"])

    op.create_table(
        "lead_form_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("form_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("lead_forms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("data", postgresql.JSONB, nullable=False),
        sa.Column("submitter_email", sa.String(255), nullable=True),
        sa.Column("submitter_name", sa.String(255), nullable=True),
        sa.Column("converted_to_deal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_lead_form_submissions_form_id", "lead_form_submissions", ["form_id"])
    op.create_index("ix_lead_form_submissions_org_id", "lead_form_submissions", ["org_id"])


def downgrade() -> None:
    op.drop_table("lead_form_submissions")
    op.drop_table("lead_forms")
