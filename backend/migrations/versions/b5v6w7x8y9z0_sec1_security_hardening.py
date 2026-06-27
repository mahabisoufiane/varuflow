"""sec1 - security hardening: audit chain, field masking, data residency, pentest reports

Revision ID: b5v6w7x8y9z0
Revises: a4u5v6w7x8y9
Create Date: 2026-04-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "b5v6w7x8y9z0"
down_revision = "a4u5v6w7x8y9"
branch_labels = None
depends_on = None

# Genesis hash value for the first row in a chain
GENESIS_HASH = "0" * 64


def upgrade() -> None:
    # ── Tamper-evident hash chain on audit_log ─────────────────────────────────
    # previous_hash: SHA-256 of the preceding row (genesis = "0"*64)
    # row_hash:      SHA-256 of (previous_hash || canonical row fields)
    op.add_column("audit_log", sa.Column(
        "previous_hash", sa.String(64), nullable=False, server_default=GENESIS_HASH
    ))
    op.add_column("audit_log", sa.Column(
        "row_hash", sa.String(64), nullable=False, server_default=GENESIS_HASH
    ))
    op.add_column("audit_log", sa.Column(
        "sequence_no", sa.BigInteger(), nullable=True, index=True
    ))  # monotonically increasing per-org for ordered verification

    # ── Data residency per org ─────────────────────────────────────────────────
    op.add_column("organizations", sa.Column(
        "data_region", sa.String(10), nullable=False, server_default="eu"
    ))  # eu | mena | us | apac

    # ── Role-based field masking rules ────────────────────────────────────────
    op.create_table(
        "field_masking_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.String(20), nullable=False),         # member|viewer|accountant
        sa.Column("resource", sa.String(50), nullable=False),     # invoice|customer|supplier|expense|payroll
        sa.Column("field", sa.String(50), nullable=False),        # total_amount|email|phone|name|bank_account|salary|cost
        sa.Column("mask_style", sa.String(20), nullable=False, server_default="obfuscate"),  # obfuscate|partial|hidden
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_id", "role", "resource", "field", name="uq_field_mask_rule"),
    )

    # ── Penetration test reports ───────────────────────────────────────────────
    op.create_table(
        "pentest_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("file_url", sa.Text(), nullable=False),         # Supabase Storage URL
        sa.Column("uploaded_by", UUID(as_uuid=True), nullable=True),
        sa.Column("test_date", sa.Date(), nullable=True),
        sa.Column("tester_name", sa.String(200), nullable=True),  # e.g. "HackerOne" / "Truesec"
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("findings_summary", sa.Text(), nullable=True),
        sa.Column("critical_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("high_count",     sa.Integer(), nullable=False, server_default="0"),
        sa.Column("medium_count",   sa.Integer(), nullable=False, server_default="0"),
        sa.Column("low_count",      sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),  # active|archived|remediated
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("pentest_reports")
    op.drop_table("field_masking_rules")
    op.drop_column("organizations", "data_region")
    op.drop_column("audit_log", "sequence_no")
    op.drop_column("audit_log", "row_hash")
    op.drop_column("audit_log", "previous_hash")
