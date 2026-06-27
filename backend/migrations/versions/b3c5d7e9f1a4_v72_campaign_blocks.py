"""v72 — Inline email campaign block editor (Item 63).

Adds a ``blocks`` JSONB column to ``campaigns`` so the inline editor
can store the structured block document alongside the rendered
``body_html``. ``body_html`` stays authoritative for sending; the
block list lets operators re-enter the editor without reverse-
engineering raw HTML.

Revision: b3c5d7e9f1a4
Revises:  a2b4c6d8e0f2 (v71 — activity feed, Item 62)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b3c5d7e9f1a4"
down_revision = "a2b4c6d8e0f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column(
            "blocks",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("campaigns", "blocks")
