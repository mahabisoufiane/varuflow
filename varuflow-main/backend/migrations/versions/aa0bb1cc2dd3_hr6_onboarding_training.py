"""hr6: employee_onboarding_tasks, employee_training_records

Revision ID: aa0bb1cc2dd3
Revises: z3t4u5v6w7x8
Create Date: 2026-04-30 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "aa0bb1cc2dd3"
down_revision = "z3t4u5v6w7x8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # employee_onboarding_tasks — per-hire checklist items
    op.create_table(
        "employee_onboarding_tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("category", sa.String(50), nullable=False, server_default="general"),
        # it_setup | access | hr_admin | equipment | intro | compliance | general
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_done", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("done_by", UUID(as_uuid=True), nullable=True),     # user_id of completer
        sa.Column("due_days_after_start", sa.Integer, nullable=True), # target completion window
        sa.Column("is_from_template", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_employee_onboarding_tasks_org_id", "employee_onboarding_tasks", ["org_id"])
    op.create_index("ix_employee_onboarding_tasks_staff_id", "employee_onboarding_tasks", ["staff_id"])

    # employee_training_records — certifications, courses, required training
    op.create_table(
        "employee_training_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_id", UUID(as_uuid=True), nullable=False),
        sa.Column("training_name", sa.String(200), nullable=False),
        sa.Column("provider", sa.String(200), nullable=True),
        sa.Column("category", sa.String(50), nullable=False, server_default="other"),
        # safety | compliance | technical | soft_skills | product | language | other
        sa.Column("status", sa.String(20), nullable=False, server_default="not_started"),
        # not_started | in_progress | completed | expired
        sa.Column("is_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("completed_at", sa.Date, nullable=True),
        sa.Column("expiry_date", sa.Date, nullable=True),
        sa.Column("required_by_date", sa.Date, nullable=True),
        sa.Column("certificate_url", sa.String(2048), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_employee_training_records_org_id", "employee_training_records", ["org_id"])
    op.create_index("ix_employee_training_records_staff_id", "employee_training_records", ["staff_id"])


def downgrade() -> None:
    op.drop_index("ix_employee_training_records_staff_id", "employee_training_records")
    op.drop_index("ix_employee_training_records_org_id", "employee_training_records")
    op.drop_table("employee_training_records")
    op.drop_index("ix_employee_onboarding_tasks_staff_id", "employee_onboarding_tasks")
    op.drop_index("ix_employee_onboarding_tasks_org_id", "employee_onboarding_tasks")
    op.drop_table("employee_onboarding_tasks")
