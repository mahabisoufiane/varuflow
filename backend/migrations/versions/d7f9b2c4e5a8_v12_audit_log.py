"""v12: audit_log table for sensitive actions

Revision ID: d7f9b2c4e5a8
Revises: c5e7f1a3d8b9
Create Date: 2026-04-21

Append-only log for GDPR deletes, plan changes, invoice write-offs,
team role changes. No UPDATE/DELETE is performed by application code.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d7f9b2c4e5a8"
down_revision = "c5e7f1a3d8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=True),
        sa.Column("target_id", sa.String(128), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("extra", postgresql.JSONB, nullable=True, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_log_org_id", "audit_log", ["org_id"])
    op.create_index("ix_audit_log_actor_user_id", "audit_log", ["actor_user_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_index("ix_audit_log_action", table_name="audit_log")
    op.drop_index("ix_audit_log_actor_user_id", table_name="audit_log")
    op.drop_index("ix_audit_log_org_id", table_name="audit_log")
    op.drop_table("audit_log")
