"""tasks and task_comments tables

Revision ID: rr8ss9tt0uu1
Revises: qq7rr8ss9tt0
Create Date: 2026-05-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "rr8ss9tt0uu1"
down_revision = "qq7rr8ss9tt0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assignee_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="todo"),
        sa.Column("priority", sa.String(10), nullable=False, server_default="medium"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parent_task_id", UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ref_type", sa.String(30), nullable=True),
        sa.Column("ref_id", UUID(as_uuid=True), nullable=True),
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("recurrence_rule", sa.String(20), nullable=True),
        sa.Column("next_recurrence", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tasks_org_assignee", "tasks", ["org_id", "assignee_id"])
    op.create_index("ix_tasks_org_status", "tasks", ["org_id", "status"])
    op.create_index("ix_tasks_org_due", "tasks", ["org_id", "due_date"])

    op.create_table(
        "task_comments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("task_id", UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_id", UUID(as_uuid=True), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_task_comments_task", "task_comments", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_task_comments_task", "task_comments")
    op.drop_table("task_comments")
    op.drop_index("ix_tasks_org_due", "tasks")
    op.drop_index("ix_tasks_org_status", "tasks")
    op.drop_index("ix_tasks_org_assignee", "tasks")
    op.drop_table("tasks")
