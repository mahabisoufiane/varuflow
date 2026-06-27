"""v42: nightly business summary email settings (Item 21).

Adds two columns to ``organizations``:

* ``nightly_summary_enabled`` (BOOL, default False) — opt-in per org so
  upgrading tenants never start receiving a new email the day after
  deploy. Owners flip it on from Settings → Notifications.
* ``nightly_summary_time`` (TIME, default 07:30) — local (Europe/Stockholm)
  send time. The scheduler runs the sweep every 15 min and each org
  fires in the quarter-hour window containing its configured time.

Both are nullable-safe through defaults so the migration is purely
additive.
"""
from alembic import op
import sqlalchemy as sa


revision = "f3a5b7c9d1e2"
down_revision = "e2f4a6b8c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "nightly_summary_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "nightly_summary_time",
            sa.Time(),
            server_default=sa.text("'07:30:00'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("organizations", "nightly_summary_time")
    op.drop_column("organizations", "nightly_summary_enabled")
