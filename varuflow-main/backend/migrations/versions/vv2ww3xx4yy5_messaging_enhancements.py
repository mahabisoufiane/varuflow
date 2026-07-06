"""messaging_enhancements — add ref_type, ref_id, attachment_url, is_pinned to staff_messages

Revision ID: vv2ww3xx4yy5
Revises: uu1vv2ww3xx4
Create Date: 2026-05-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "vv2ww3xx4yy5"
down_revision = "uu1vv2ww3xx4"
branch_labels = None
# cross-branch ordering: staff_messages live on parallel branches — apply first
depends_on = "hh7ii8jj9kk0"
def upgrade() -> None:
    op.add_column("staff_messages", sa.Column("ref_type", sa.String(50), nullable=True))
    op.add_column("staff_messages", sa.Column("ref_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("staff_messages", sa.Column("attachment_url", sa.Text, nullable=True))
    op.add_column("staff_messages", sa.Column("is_pinned", sa.Boolean, nullable=False, server_default="false"))
    op.add_column("staff_messages", sa.Column("mentions", postgresql.JSONB, nullable=True))
    op.create_index("ix_staff_messages_ref", "staff_messages", ["ref_type", "ref_id"])

    op.create_table(
        "staff_dnd_hours",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("staff_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("dnd_start", sa.String(5), nullable=False, server_default="22:00"),
        sa.Column("dnd_end", sa.String(5), nullable=False, server_default="08:00"),
        sa.Column("dnd_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_staff_dnd_staff_id", "staff_dnd_hours", ["staff_id"])


def downgrade() -> None:
    op.drop_table("staff_dnd_hours")
    op.drop_index("ix_staff_messages_ref", "staff_messages")
    op.drop_column("staff_messages", "mentions")
    op.drop_column("staff_messages", "is_pinned")
    op.drop_column("staff_messages", "attachment_url")
    op.drop_column("staff_messages", "ref_id")
    op.drop_column("staff_messages", "ref_type")
