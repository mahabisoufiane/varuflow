"""v20: dunning automation — invoice dunning stage + dunning_events history

Revision ID: f0a2c4e6d8b1
Revises: e9f1a3c5b7d2
Create Date: 2026-04-22

Tracks automated payment reminders sent against overdue invoices.
Each outbound reminder email increments ``invoices.dunning_stage``
and writes a row to ``dunning_events`` so the timeline is auditable
and idempotent — re-running the scheduled job for the same calendar
day should never resend an already-sent stage.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f0a2c4e6d8b1"
down_revision = "e9f1a3c5b7d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column(
            "dunning_stage",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "last_dunning_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_table(
        "dunning_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # 1 = friendly (+3d), 2 = firm (+7d), 3 = final notice (+14d),
        # 4 = legal escalation (+30d). Higher stages reserved.
        sa.Column("stage", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False, server_default="email"),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # Pinned trigger — "scheduler" (automatic) or "manual"
        sa.Column("trigger", sa.String(20), nullable=False, server_default="scheduler"),
        # Unique per (invoice, stage) so the scheduler is idempotent —
        # running the daily job twice cannot double-send the same stage.
        sa.UniqueConstraint("invoice_id", "stage", name="uq_dunning_events_invoice_stage"),
    )
    op.create_index(
        "ix_dunning_events_sent_at", "dunning_events", ["sent_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_dunning_events_sent_at", table_name="dunning_events")
    op.drop_table("dunning_events")
    op.drop_column("invoices", "last_dunning_sent_at")
    op.drop_column("invoices", "dunning_stage")
