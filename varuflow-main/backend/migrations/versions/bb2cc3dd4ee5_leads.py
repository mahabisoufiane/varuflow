"""Lead management: leads table + lead score events

Revision ID: bb2cc3dd4ee5
Revises: aa1bb2cc3dd4
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "bb2cc3dd4ee5"
down_revision = "aa1bb2cc3dd4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("company", sa.String(300), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("assigned_to", UUID(as_uuid=True),
                  nullable=True),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("lead_form_submission_id", UUID(as_uuid=True),
                  sa.ForeignKey("lead_form_submissions.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("converted_customer_id", UUID(as_uuid=True),
                  sa.ForeignKey("customers.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("converted_deal_id", UUID(as_uuid=True),
                  sa.ForeignKey("deals.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_leads_org_id", "leads", ["org_id"])
    op.create_index("ix_leads_org_status", "leads", ["org_id", "status"])
    op.create_index("ix_leads_org_email", "leads", ["org_id", "email"])
    op.create_index("ix_leads_assigned_to", "leads", ["assigned_to"])

    op.create_table(
        "lead_score_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("lead_id", UUID(as_uuid=True),
                  sa.ForeignKey("leads.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_lead_score_events_lead_id", "lead_score_events", ["lead_id"])


def downgrade() -> None:
    op.drop_index("ix_lead_score_events_lead_id", "lead_score_events")
    op.drop_table("lead_score_events")
    op.drop_index("ix_leads_assigned_to", "leads")
    op.drop_index("ix_leads_org_email", "leads")
    op.drop_index("ix_leads_org_status", "leads")
    op.drop_index("ix_leads_org_id", "leads")
    op.drop_table("leads")
