"""e-signature and gdpr consent tables.

Revision ID: nn4oo5pp6qq7
Revises: z3t4u5v6w7x8
Create Date: 2026-05-01

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "nn4oo5pp6qq7"
down_revision = "z3t4u5v6w7x8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── E-Signature ──────────────────────────────────────────────────────────
    op.create_table(
        "esign_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("reminder_days", sa.Integer, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("signed_pdf_url", sa.Text, nullable=True),
        sa.Column("audit_certificate_url", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_esign_requests_org_id", "esign_requests", ["org_id"])
    op.create_index("ix_esign_requests_org_status", "esign_requests", ["org_id", "status"])

    op.create_table(
        "esign_signatories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("email", sa.String(500), nullable=False),
        sa.Column("role", sa.String(200), nullable=True),
        sa.Column("sign_order", sa.Integer, server_default="1"),
        sa.Column("token", sa.String(128), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("declined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decline_reason", sa.Text, nullable=True),
        sa.Column("signature_data", postgresql.JSONB, nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["request_id"], ["esign_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index("ix_esign_signatories_request_id", "esign_signatories", ["request_id"])

    op.create_table(
        "esign_audit_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("actor_email", sa.String(500), nullable=True),
        sa.Column("actor_name", sa.String(300), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["request_id"], ["esign_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_esign_audit_entries_request_id", "esign_audit_entries", ["request_id"])

    # ── GDPR Consent ─────────────────────────────────────────────────────────
    op.create_table(
        "consent_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consent_type", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="given"),
        sa.Column("collected_via", sa.String(40), nullable=False, server_default="staff"),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("consented_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consent_records_org_customer", "consent_records", ["org_id", "customer_id"])
    op.create_index("ix_consent_records_org_type", "consent_records", ["org_id", "consent_type", "status"])

    op.create_table(
        "consent_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("consent_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("consent_type", sa.String(80), nullable=True),
        sa.Column("actor", sa.String(200), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("extra", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consent_audit_log_org_id", "consent_audit_log", ["org_id"])

    op.create_table(
        "dsar_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_type", sa.String(40), nullable=False, server_default="access"),
        sa.Column("requester_name", sa.String(300), nullable=False),
        sa.Column("requester_email", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("response_notes", sa.Text, nullable=True),
        sa.Column("response_package_url", sa.Text, nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dsar_requests_org_id", "dsar_requests", ["org_id"])
    op.create_index("ix_dsar_requests_org_status", "dsar_requests", ["org_id", "status"])


def downgrade() -> None:
    op.drop_table("dsar_requests")
    op.drop_table("consent_audit_log")
    op.drop_table("consent_records")
    op.drop_table("esign_audit_entries")
    op.drop_table("esign_signatories")
    op.drop_table("esign_requests")
