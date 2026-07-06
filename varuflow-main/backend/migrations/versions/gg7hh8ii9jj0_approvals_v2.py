"""approvals v2 — escalation, PO/quote status, delegates

Revision ID: gg7hh8ii9jj0
Revises: ff6gg7hh8ii9
Create Date: 2026-04-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "gg7hh8ii9jj0"
# This migration ALTERs approval_rules/approval_requests (created by governance,
# f9z0a1b2c3d4). Both were parallel parents of the final merge, so ordering them
# via depends_on broke alembic's merge head-tracking (KeyError). Express it as a
# real down_revision edge instead; f9z0a1b2c3d4 is then dropped from the merge.
down_revision = ("ff6gg7hh8ii9", "f9z0a1b2c3d4")
branch_labels = None
# quotes (ee4ff5gg6hh7) is interior to another branch (not a merge parent) — depends_on is safe.
depends_on = "ee4ff5gg6hh7"
def upgrade() -> None:
    # approval_rules: escalation config + CEO notification email
    op.add_column("approval_rules", sa.Column("escalation_days", sa.Integer, nullable=True))
    op.add_column("approval_rules", sa.Column("notify_email",    sa.String(254), nullable=True))

    # approval_requests: track escalation
    op.add_column("approval_requests", sa.Column("escalated_at",       sa.DateTime(timezone=True), nullable=True))
    op.add_column("approval_requests", sa.Column("escalated_to_role",  sa.String(20), nullable=True))

    # purchase_orders: gate purchases behind approval flow
    op.add_column("purchase_orders", sa.Column("approval_status", sa.String(20), nullable=True))

    # quotes: require approval before sending to customer
    op.add_column("quotes", sa.Column("approval_status", sa.String(20), nullable=True))

    # approval_delegates — "Alice covers Bob while Bob is on leave"
    op.create_table(
        "approval_delegates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("delegated_from_role",   sa.String(20),  nullable=False),   # OWNER | ADMIN
        sa.Column("delegated_to_user_id",  UUID(as_uuid=True), nullable=False),
        sa.Column("delegated_to_email",    sa.String(254), nullable=True),
        sa.Column("valid_from",  sa.Date, nullable=False),
        sa.Column("valid_until", sa.Date, nullable=False),
        sa.Column("note",       sa.String(300), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_approval_delegates_org_id",    "approval_delegates", ["org_id"])
    op.create_index("ix_approval_delegates_valid_span","approval_delegates", ["org_id", "valid_from", "valid_until"])


def downgrade() -> None:
    op.drop_index("ix_approval_delegates_valid_span", "approval_delegates")
    op.drop_index("ix_approval_delegates_org_id",     "approval_delegates")
    op.drop_table("approval_delegates")
    op.drop_column("quotes",            "approval_status")
    op.drop_column("purchase_orders",   "approval_status")
    op.drop_column("approval_requests", "escalated_to_role")
    op.drop_column("approval_requests", "escalated_at")
    op.drop_column("approval_rules",    "notify_email")
    op.drop_column("approval_rules",    "escalation_days")
