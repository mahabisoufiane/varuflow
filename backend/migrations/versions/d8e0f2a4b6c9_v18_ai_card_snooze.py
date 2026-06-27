"""v18: ai_card_snooze table for dismissible AI action cards

Revision ID: d8e0f2a4b6c9
Revises: c5d7e9f1a3b6
Create Date: 2026-04-22

Allows a user to snooze an AI action card (e.g. dead-stock flag) for
7/30/90 days. The (org_id, card_type, product_id) triple is unique
because every product/card combination should only ever hold one
active snooze — a second snooze overwrites the first via UPSERT from
the /api/ai/cards/{id}/snooze endpoint.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d8e0f2a4b6c9"
down_revision = "c5d7e9f1a3b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_card_snooze",
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
        sa.Column("card_type", sa.String(64), nullable=False),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "org_id", "card_type", "product_id",
            name="uq_ai_card_snooze_org_card_product",
        ),
    )
    op.create_index(
        "ix_ai_card_snooze_snoozed_until",
        "ai_card_snooze",
        ["snoozed_until"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_card_snooze_snoozed_until", table_name="ai_card_snooze")
    op.drop_table("ai_card_snooze")
