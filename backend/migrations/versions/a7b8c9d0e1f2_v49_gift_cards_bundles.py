"""v49 — gift cards & service bundles (Item 33).

Creates three tables:
- gift_cards          — issued cards with remaining balance
- service_bundles     — package definitions (N sessions of services)
- bundle_redemptions  — per-use records linking a bundle to an appointment

Revision: a7b8c9d0e1f2
Revises:  f9a1b3c5d7e2  (v48 — commissions)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "a7b8c9d0e1f2"
down_revision = "f9a1b3c5d7e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gift_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("initial_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("remaining_value", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "issued_to_customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        # active | redeemed | expired | void
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_id", "code", name="uq_gift_cards_org_code"),
    )
    op.create_index("ix_gift_cards_code", "gift_cards", ["code"])

    op.create_table(
        "service_bundles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("valid_days", sa.Integer(), nullable=False, server_default="365"),
        # JSONB array of service UUIDs (stringified)
        sa.Column(
            "services",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("sessions_total", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # A "customer bundle" is a bundle purchased by a customer; each
    # redemption consumes one session. We track purchases as
    # redemptions rows with sessions_used derived from count, keeping
    # the schema shallow per the spec.
    op.create_table(
        "bundle_redemptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "bundle_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("service_bundles.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "appointment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("appointments.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        # "purchase" marks the initial sale; subsequent rows are "use".
        sa.Column("kind", sa.String(16), nullable=False, server_default="use"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("bundle_redemptions")
    op.drop_table("service_bundles")
    op.drop_index("ix_gift_cards_code", table_name="gift_cards")
    op.drop_table("gift_cards")
