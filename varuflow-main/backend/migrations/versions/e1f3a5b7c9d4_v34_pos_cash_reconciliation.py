"""v34 POS session cash reconciliation.

Adds the cash-drawer fields used by the tablet POS Z-report modal:

* ``opening_float``    — cash put into the drawer when the session is
                         opened (Swedish ``öppningskassa``). Used as the
                         baseline for cash-variance calculation.
* ``counted_cash``     — actual cash counted by the cashier at close.
* ``variance``         — ``counted_cash − expected_cash``. Persisted so
                         the Z-report PDF and the dashboard render the
                         same number (kassalagen compliance: the close
                         record must be immutable after sign-off).

All three columns are nullable because every session opened before this
migration has no float data — we cannot invent historical values.

Revises c9d1e3f5a8b2 via d0e2f4a6b8c3. New chain head = e1f3a5b7c9d4.
"""
from alembic import op
import sqlalchemy as sa

revision = "e1f3a5b7c9d4"
down_revision = "d0e2f4a6b8c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pos_sessions",
        sa.Column("opening_float", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "pos_sessions",
        sa.Column("counted_cash", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "pos_sessions",
        sa.Column("variance", sa.Numeric(14, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pos_sessions", "variance")
    op.drop_column("pos_sessions", "counted_cash")
    op.drop_column("pos_sessions", "opening_float")
