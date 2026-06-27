"""gov1: approval_rules, approval_requests, policy_documents; signing columns on contracts; approval_status on invoices/expenses

Revision ID: f9z0a1b2c3d4
Revises: e8y9z0a1b2c3
Create Date: 2026-04-30 11:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "f9z0a1b2c3d4"
down_revision = "e8y9z0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # approval_rules — configurable threshold rules per resource type
    op.create_table(
        "approval_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_type", sa.String(20), nullable=False),   # invoice | expense
        sa.Column("threshold_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("required_approver_role", sa.String(20), nullable=False, server_default="OWNER"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_approval_rules_org_id", "approval_rules", ["org_id"])

    # approval_requests — one row per pending/resolved approval action
    op.create_table(
        "approval_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_id", UUID(as_uuid=True), sa.ForeignKey("approval_rules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resource_type", sa.String(20), nullable=False),
        sa.Column("resource_id", UUID(as_uuid=True), nullable=False),
        sa.Column("resource_label", sa.String(200), nullable=True),   # e.g. "INV-2026-0042 — Acme Corp"
        sa.Column("amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SEK"),
        sa.Column("requested_by", UUID(as_uuid=True), nullable=False),   # user_id of submitter
        sa.Column("requested_by_email", sa.String(254), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("reviewed_by", UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),  # pending|approved|rejected
        sa.Column("reviewer_note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_approval_requests_org_id", "approval_requests", ["org_id"])
    op.create_index("ix_approval_requests_resource_id", "approval_requests", ["resource_id"])
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])

    # policy_documents — company policies accessible to all staff
    op.create_table(
        "policy_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("category", sa.String(50), nullable=False, server_default="other"),
        # hr | finance | it | legal | operations | security | other
        sa.Column("content", sa.Text, nullable=False, server_default=""),
        sa.Column("is_published", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_policy_documents_org_id", "policy_documents", ["org_id"])

    # Add approval_status column to invoices (nullable = not in approval flow)
    op.add_column("invoices", sa.Column("approval_status", sa.String(20), nullable=True))
    # null = not required, 'pending' = awaiting approval, 'approved' = approved, 'rejected' = rejected

    # Add approval_required to expenses (approval_status tracked via ApprovalRequest)
    op.add_column("expenses", sa.Column("approval_required", sa.Boolean, nullable=False, server_default="false"))

    # Add digital signature columns to customer_contracts
    op.add_column("customer_contracts", sa.Column("signer_name", sa.String(200), nullable=True))
    op.add_column("customer_contracts", sa.Column("signer_email", sa.String(254), nullable=True))
    op.add_column("customer_contracts", sa.Column("signature_hash", sa.String(64), nullable=True))
    # SHA256 hex of: contract body + signer name + signer email + signed_at ISO


def downgrade() -> None:
    op.drop_column("customer_contracts", "signature_hash")
    op.drop_column("customer_contracts", "signer_email")
    op.drop_column("customer_contracts", "signer_name")
    op.drop_column("expenses", "approval_required")
    op.drop_column("invoices", "approval_status")
    op.drop_index("ix_policy_documents_org_id", "policy_documents")
    op.drop_table("policy_documents")
    op.drop_index("ix_approval_requests_status", "approval_requests")
    op.drop_index("ix_approval_requests_resource_id", "approval_requests")
    op.drop_index("ix_approval_requests_org_id", "approval_requests")
    op.drop_table("approval_requests")
    op.drop_index("ix_approval_rules_org_id", "approval_rules")
    op.drop_table("approval_rules")
