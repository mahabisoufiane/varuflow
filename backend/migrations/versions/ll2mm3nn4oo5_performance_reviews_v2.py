"""Performance review v2: cycle_frequency, rating_labels, check_in_notes, development_plan.

Revision ID: ll2mm3nn4oo5
Revises: kk1ll2mm3nn4
Create Date: 2026-05-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "ll2mm3nn4oo5"
down_revision = "kk1ll2mm3nn4"
branch_labels = None
depends_on = None

_DEFAULT_LABELS = '["Unsatisfactory","Below Expectations","Meets Expectations","Exceeds Expectations","Outstanding"]'


def upgrade() -> None:
    op.add_column("performance_cycles",
        sa.Column("cycle_frequency", sa.String(20), nullable=False, server_default="annual"))
    op.add_column("performance_cycles",
        sa.Column("rating_labels", JSONB, nullable=False,
                  server_default=_DEFAULT_LABELS))

    op.add_column("performance_reviews",
        sa.Column("check_in_notes", sa.Text, nullable=True))
    op.add_column("performance_reviews",
        sa.Column("development_plan", JSONB, nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("performance_reviews", "development_plan")
    op.drop_column("performance_reviews", "check_in_notes")
    op.drop_column("performance_cycles", "rating_labels")
    op.drop_column("performance_cycles", "cycle_frequency")
