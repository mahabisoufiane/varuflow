"""announcements and announcement_reads tables

Revision ID: ss9tt0uu1vv2
Revises: rr8ss9tt0uu1
Create Date: 2026-05-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "ss9tt0uu1vv2"
down_revision = "rr8ss9tt0uu1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "announcements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("author_id", UUID(as_uuid=True), sa.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True),
        sa.Column("category", sa.String(30), nullable=False, server_default="operational"),
        sa.Column("target_role", sa.String(30), nullable=True),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("acknowledgement_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("emoji_reactions", sa.JSON(), nullable=True),  # {emoji: count, ...}
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_announcements_org", "announcements", ["org_id"])

    op.create_table(
        "announcement_reads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("announcement_id", UUID(as_uuid=True), sa.ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_id", UUID(as_uuid=True), sa.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("announcement_id", "staff_id", name="uq_ann_reads"),
    )
    op.create_index("ix_ann_reads_announcement", "announcement_reads", ["announcement_id"])
    op.create_index("ix_ann_reads_staff", "announcement_reads", ["staff_id"])


def downgrade() -> None:
    op.drop_index("ix_ann_reads_staff", "announcement_reads")
    op.drop_index("ix_ann_reads_announcement", "announcement_reads")
    op.drop_table("announcement_reads")
    op.drop_index("ix_announcements_org", "announcements")
    op.drop_table("announcements")
