"""v61 — Subscription pause & resume (Item 50).

Two changes:

* Adds five pause-tracking columns to ``organizations``:

  - ``is_paused`` (bool, default false) — the hot flag the write-guard
    middleware reads on every mutating request. Indexed so the
    "list all paused orgs" sweep stays cheap.
  - ``paused_at`` — when the current pause started.
  - ``pause_ends_at`` — scheduled auto-resume moment.
  - ``pause_reminder_sent_at`` — flips when the 7-day warning email
    ships so the scheduler doesn't double-send.
  - ``stripe_subscription_id`` — required to call
    ``Subscription.modify(pause_collection=...)``. Only
    ``stripe_customer_id`` existed before.

* ``subscription_pauses`` — append-only history row per pause. One
  row per pause window; ``ended_at`` NULL means the pause is still
  active.

Spec asked for v??; taking v61 — the next free slot after v60
reviews (convention used throughout §§58-§77).

Revision: c1d3e5f7a9b2
Revises:  b9c2d4e6f8a1 (v60 — reviews, Item 49)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c1d3e5f7a9b2"
down_revision = "b9c2d4e6f8a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── organizations — pause tracking columns ──────────────────────
    op.add_column(
        "organizations",
        sa.Column(
            "is_paused",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "organizations",
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("pause_ends_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "pause_reminder_sent_at", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "stripe_subscription_id", sa.String(length=100), nullable=True
        ),
    )
    # Partial index — the middleware and scheduler sweep only ever
    # ask "which orgs are paused right now?"
    op.create_index(
        "ix_organizations_is_paused",
        "organizations",
        ["id"],
        postgresql_where=sa.text("is_paused = true"),
    )

    # ── subscription_pauses — append-only history ───────────────────
    op.create_table(
        "subscription_pauses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # NULL while the pause is still open; set when resume fires.
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        # When auto-resume would kick in. Stored on the history row
        # so a subsequent manual resume doesn't destroy the intended
        # window for audit.
        sa.Column(
            "scheduled_resume_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "reason", sa.String(length=128), nullable=True
        ),
        # ``owner_request`` / ``payment_failed`` / ``auto_resume`` —
        # keeps it short so it indexes well without an enum migration.
        sa.Column(
            "resume_reason", sa.String(length=64), nullable=True
        ),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_subscription_pauses_org",
        "subscription_pauses",
        ["org_id"],
    )
    # Partial index on the one-open-pause-per-org predicate — the
    # router's "is there an active pause already?" lookup.
    op.create_index(
        "ix_subscription_pauses_active",
        "subscription_pauses",
        ["org_id"],
        postgresql_where=sa.text("ended_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_subscription_pauses_active", table_name="subscription_pauses")
    op.drop_index("ix_subscription_pauses_org", table_name="subscription_pauses")
    op.drop_table("subscription_pauses")
    op.drop_index("ix_organizations_is_paused", table_name="organizations")
    op.drop_column("organizations", "stripe_subscription_id")
    op.drop_column("organizations", "pause_reminder_sent_at")
    op.drop_column("organizations", "pause_ends_at")
    op.drop_column("organizations", "paused_at")
    op.drop_column("organizations", "is_paused")
