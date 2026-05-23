"""v71 — Activity feed events (Item 62).

User-facing activity timeline, separate from the security-focused
``audit_log``. Every event links to an org and an optional entity
(customer, invoice, product, appointment, etc.) and carries a short
summary plus optional structured metadata.

Kept distinct from ``audit_log`` because:
* Audit rows are written by every mutating endpoint for compliance;
  users don't want to see them all.
* Activity rows are curated signals worth surfacing in a feed
  ("Invoice #42 sent to customer X", "Customer Bob left a review").

Revision: a2b4c6d8e0f2
Revises:  f0b2d4e6a8c1 (v70 — saved filters, Item 61)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a2b4c6d8e0f2"
down_revision = "f0b2d4e6a8c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Actor is a Supabase user_id; may be NULL for system-generated
        # events (dunning, scheduled jobs, webhooks).
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        # Dot-separated: "invoice.sent", "customer.created",
        # "appointment.checked_in", "note.added".
        sa.Column("action", sa.String(length=64), nullable=False),
        # Optional entity link. When both NULL the event is org-wide
        # (e.g. "settings.updated").
        sa.Column("entity_type", sa.String(length=32), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        # Short human-readable summary, rendered as-is in the UI.
        sa.Column("summary", sa.String(length=255), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # Newest-first listing per org.
    op.create_index(
        "ix_activity_org_created",
        "activity_events",
        ["org_id", sa.text("created_at DESC")],
    )
    # Entity timeline lookup.
    op.create_index(
        "ix_activity_entity",
        "activity_events",
        ["org_id", "entity_type", "entity_id"],
    )
    # Filter by actor.
    op.create_index(
        "ix_activity_actor",
        "activity_events",
        ["org_id", "actor_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_activity_actor", table_name="activity_events")
    op.drop_index("ix_activity_entity", table_name="activity_events")
    op.drop_index("ix_activity_org_created", table_name="activity_events")
    op.drop_table("activity_events")
