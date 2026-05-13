"""v31: health_checks + status_incidents

Revision ID: d0e2f4a6b8c3
Revises: c9d1e3f5a8b2
Create Date: 2026-04-23

Backs the public /status page. ``health_checks`` is appended every 5
minutes by the scheduler probe; ``status_incidents`` is curated by
operators via an admin endpoint to surface real outages on the page.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d0e2f4a6b8c3"
down_revision = "c9d1e3f5a8b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "health_checks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("db_ok", sa.Boolean(), nullable=False),
        sa.Column("stripe_ok", sa.Boolean(), nullable=False),
        sa.Column("resend_ok", sa.Boolean(), nullable=False),
        sa.Column("response_ms", sa.Integer(), nullable=False),
    )
    # Status page reads ORDER BY checked_at DESC and aggregates by day —
    # an index on the timestamp keeps the 90-day rollup cheap even when
    # the table grows to ~26k rows/year per service.
    op.create_index(
        "ix_health_checks_checked_at",
        "health_checks",
        ["checked_at"],
    )

    op.create_table(
        "status_incidents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "severity",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'minor'"),
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_status_incidents_started_at",
        "status_incidents",
        ["started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_status_incidents_started_at", table_name="status_incidents")
    op.drop_table("status_incidents")
    op.drop_index("ix_health_checks_checked_at", table_name="health_checks")
    op.drop_table("health_checks")
