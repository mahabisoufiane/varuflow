"""ai1 - workflow rules

Revision ID: v9p1q2r3s4t5
Revises: u0o1p2q3r4s5
Create Date: 2026-04-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "v9p1q2r3s4t5"
down_revision = "u0o1p2q3r4s5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("trigger_type", sa.String(50), nullable=False),
        sa.Column("trigger_conditions", JSONB(), nullable=False, server_default="{}"),
        sa.Column("actions", JSONB(), nullable=False, server_default="[]"),
        sa.Column("run_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("workflow_rules")
