"""v26: onboarding_progress

Revision ID: f6a8c0e2d4b5
Revises: e5f7b9d1c3a4
Create Date: 2026-04-22

Tracks per-org completion of the new onboarding checklist. One row
per (org_id, step) pair — unique constraint prevents double-counting
when the same step is re-submitted.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f6a8c0e2d4b5"
down_revision = "e5f7b9d1c3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "onboarding_progress",
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
        # Free-form string rather than an enum so adding a new step
        # (e.g. CONNECT_STRIPE) does not require a schema migration.
        # The allowed set is validated at the router layer.
        sa.Column("step", sa.String(length=64), nullable=False),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("org_id", "step", name="uq_onboarding_progress_org_step"),
    )


def downgrade() -> None:
    op.drop_table("onboarding_progress")
