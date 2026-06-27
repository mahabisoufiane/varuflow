"""Operational Excellence — SOP Library, Checklist Templates, Recurring Reminders, Decision Log.

Revision ID: ee5ff6gg7hh8
Revises:     dd3ee4ff5gg6
Create Date: 2026-05-01
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "ee5ff6gg7hh8"
down_revision = "dd3ee4ff5gg6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── sop_documents ───────────────────────────────────────────────────────────
    op.create_table(
        "sop_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("content_markdown", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("org_id", "slug", name="uq_sop_documents_org_slug"),
    )
    op.create_index("ix_sop_documents_org_id", "sop_documents", ["org_id"])

    op.create_table(
        "sop_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("sop_id", UUID(as_uuid=True),
                  sa.ForeignKey("sop_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=True),
        sa.Column("changed_by", UUID(as_uuid=True), nullable=True),
        sa.Column("change_notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_sop_versions_sop_id", "sop_versions", ["sop_id"])

    # ── checklist_templates ──────────────────────────────────────────────────────
    op.create_table(
        "checklist_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("frequency", sa.String(30), nullable=False, server_default="manual"),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_checklist_templates_org_id", "checklist_templates", ["org_id"])

    op.create_table(
        "checklist_template_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("template_id", UUID(as_uuid=True),
                  sa.ForeignKey("checklist_templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_checklist_template_items_template_id",
                    "checklist_template_items", ["template_id"])

    op.create_table(
        "checklist_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("template_id", UUID(as_uuid=True),
                  sa.ForeignKey("checklist_templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_by", UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("started_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_checklist_runs_template_id", "checklist_runs", ["template_id"])
    op.create_index("ix_checklist_runs_org_id", "checklist_runs", ["org_id"])

    op.create_table(
        "checklist_run_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("run_id", UUID(as_uuid=True),
                  sa.ForeignKey("checklist_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_item_id", UUID(as_uuid=True),
                  sa.ForeignKey("checklist_template_items.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("is_checked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("checked_by", UUID(as_uuid=True), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_checklist_run_items_run_id", "checklist_run_items", ["run_id"])

    # ── recurring_reminders ──────────────────────────────────────────────────────
    op.create_table(
        "recurring_reminders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("frequency", sa.String(20), nullable=False, server_default="weekly"),
        sa.Column("day_of_week", sa.Integer(), nullable=True),
        sa.Column("day_of_month", sa.Integer(), nullable=True),
        sa.Column("time_of_day", sa.String(8), nullable=False, server_default="09:00"),
        sa.Column("assigned_to_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_recurring_reminders_org_id", "recurring_reminders", ["org_id"])
    op.create_index("ix_recurring_reminders_next_due", "recurring_reminders", ["next_due_at"])

    op.create_table(
        "reminder_occurrences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("reminder_id", UUID(as_uuid=True),
                  sa.ForeignKey("recurring_reminders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_reminder_occurrences_reminder_id",
                    "reminder_occurrences", ["reminder_id"])
    op.create_index("ix_reminder_occurrences_due_at", "reminder_occurrences", ["due_at"])

    # ── decision_log ─────────────────────────────────────────────────────────────
    op.create_table(
        "decision_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("decided_at", sa.Date(), nullable=False),
        sa.Column("decided_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("decided_by_name", sa.String(200), nullable=True),
        sa.Column("area", sa.String(100), nullable=True),
        sa.Column("decision_summary", sa.Text(), nullable=False),
        sa.Column("alternatives_considered", sa.Text(), nullable=True),
        sa.Column("expected_outcome", sa.Text(), nullable=True),
        sa.Column("actual_outcome", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_decision_log_org_id", "decision_log", ["org_id"])
    op.create_index("ix_decision_log_decided_at", "decision_log", ["decided_at"])


def downgrade() -> None:
    op.drop_table("decision_log")
    op.drop_table("reminder_occurrences")
    op.drop_table("recurring_reminders")
    op.drop_table("checklist_run_items")
    op.drop_table("checklist_runs")
    op.drop_table("checklist_template_items")
    op.drop_table("checklist_templates")
    op.drop_table("sop_versions")
    op.drop_table("sop_documents")
