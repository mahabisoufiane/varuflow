"""anomaly detection + cash flow scenario tables

Revision ID: jj0kk1ll2mm3
Revises: ii9jj0kk1ll2
Create Date: 2026-05-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "jj0kk1ll2mm3"
down_revision = "ii9jj0kk1ll2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "anomaly_findings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), nullable=False),
        sa.Column("anomaly_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("context", JSONB(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", UUID(as_uuid=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
    )
    op.create_index("ix_anomaly_findings_org_id", "anomaly_findings", ["org_id"])
    op.create_index("ix_anomaly_findings_status", "anomaly_findings", ["status"])
    op.create_index("ix_anomaly_findings_type", "anomaly_findings", ["anomaly_type"])

    op.create_table(
        "cashflow_scenarios",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("monthly_delta", sa.Numeric(14, 2), nullable=False),
        sa.Column("months_duration", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_cashflow_scenarios_org_id", "cashflow_scenarios", ["org_id"])


def downgrade() -> None:
    op.drop_table("cashflow_scenarios")
    op.drop_table("anomaly_findings")
