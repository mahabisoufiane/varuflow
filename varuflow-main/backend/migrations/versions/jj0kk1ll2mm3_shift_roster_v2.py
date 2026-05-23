"""shift roster v2 — color, roster_week, publications, swap router support

Revision ID: jj0kk1ll2mm3
Revises: ii9jj0kk1ll2
Create Date: 2026-04-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "jj0kk1ll2mm3"
down_revision = "ii9jj0kk1ll2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # shifts: per-shift colour (inherits staff colour in UI) + week label
    op.add_column("shifts", sa.Column("color", sa.String(7), nullable=True))
    op.add_column("shifts", sa.Column("roster_week", sa.String(10), nullable=True))  # e.g. "2026-W18"
    op.create_index("ix_shifts_org_roster_week", "shifts", ["org_id", "roster_week"])

    # shift_swap_requests: message field for requester note
    op.add_column("shift_swap_requests", sa.Column("requester_note", sa.Text, nullable=True))

    # roster_publications — track which weeks have been published and when
    op.create_table(
        "roster_publications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week_start", sa.Date, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("published_by", UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_roster_publications_org_id", "roster_publications", ["org_id"])
    op.create_unique_constraint("uq_roster_publications_org_week", "roster_publications", ["org_id", "week_start"])


def downgrade() -> None:
    op.drop_table("roster_publications")
    op.drop_column("shift_swap_requests", "requester_note")
    op.drop_index("ix_shifts_org_roster_week", "shifts")
    op.drop_column("shifts", "roster_week")
    op.drop_column("shifts", "color")
