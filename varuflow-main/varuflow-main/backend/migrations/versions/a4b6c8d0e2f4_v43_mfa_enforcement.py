"""v43: TOTP / MFA enforcement (Item 23).

Adds ``auth_users.totp_enforced_at`` — a nullable timestamp that records
the instant MFA was activated on the account. It doubles as a
"who-first-tripped-the-enforcement-rule" audit field without needing a
separate table.

The column is nullable because:

* Users who enabled TOTP before enforcement shipped have
  ``totp_enabled=True`` but no recorded enforcement time — backfilling a
  synthetic timestamp would be misleading (we don't actually know when
  they first met the enforcement rule).
* Users who disable TOTP need the column cleared so a future re-enable
  records the new timestamp.

Purely additive migration — a default of NULL means existing rows need
no backfill and no downtime.
"""
from alembic import op
import sqlalchemy as sa


revision = "a4b6c8d0e2f4"
down_revision = "f3a5b7c9d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "auth_users",
        sa.Column(
            "totp_enforced_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("auth_users", "totp_enforced_at")
