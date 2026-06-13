"""Training requests and mandatory role requirements.

Revision ID: mm3nn4oo5pp6
Revises: ll2mm3nn4oo5
Create Date: 2026-05-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "mm3nn4oo5pp6"
down_revision = "ll2mm3nn4oo5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Mandatory training required for a given job role
    op.create_table(
        "mandatory_training_requirements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_role", sa.String(100), nullable=False),
        sa.Column("training_name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(50), nullable=False, server_default="other"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_id", "job_role", "training_name",
                            name="uq_mandatory_training_org_role_name"),
    )
    op.create_index("ix_mandatory_training_org_id", "mandatory_training_requirements", ["org_id"])

    # Self-service training requests (staff requests a course, manager approves)
    op.create_table(
        "training_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_id", UUID(as_uuid=True),
                  sa.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False),
        sa.Column("training_name", sa.String(200), nullable=False),
        sa.Column("provider", sa.String(200), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("justification", sa.Text, nullable=True),
        # pending | approved | rejected | completed
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("manager_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_training_requests_org_id", "training_requests", ["org_id"])
    op.create_index("ix_training_requests_staff_id", "training_requests", ["staff_id"])


def downgrade() -> None:
    op.drop_table("training_requests")
    op.drop_table("mandatory_training_requirements")
