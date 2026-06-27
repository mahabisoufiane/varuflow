"""ticket sla fields and internal notes

Revision ID: oo5pp6qq7rr8
Revises: nn4oo5pp6qq7
Create Date: 2026-04-30

"""
from alembic import op
import sqlalchemy as sa

revision = "oo5pp6qq7rr8"
down_revision = "nn4oo5pp6qq7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("portal_tickets", sa.Column("ticket_type", sa.String(30), nullable=True))
    op.add_column("portal_tickets", sa.Column("sla_hours", sa.Integer(), nullable=True))
    op.add_column("portal_tickets", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("portal_tickets", sa.Column("csat_token", sa.String(64), nullable=True))
    op.create_index("ix_portal_tickets_org_status", "portal_tickets", ["org_id", "status"])
    op.add_column("portal_ticket_replies", sa.Column("is_internal", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("portal_ticket_replies", "is_internal")
    op.drop_index("ix_portal_tickets_org_status", "portal_tickets")
    op.drop_column("portal_tickets", "csat_token")
    op.drop_column("portal_tickets", "resolved_at")
    op.drop_column("portal_tickets", "sla_hours")
    op.drop_column("portal_tickets", "ticket_type")
