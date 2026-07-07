"""chatbot_configs.fallback_message — org-configurable bot fallback reply

The portal chat bot's "couldn't find an answer" reply was hardcoded
English; Swedish orgs need to configure it like the welcome message.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-07-07
"""
from alembic import op

revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS: environments that (re)created the table via
    # Base.metadata.create_all after the model change already have the
    # column — same guard pattern as the audit-chain migration.
    op.execute(
        "ALTER TABLE chatbot_configs ADD COLUMN IF NOT EXISTS fallback_message TEXT"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE chatbot_configs DROP COLUMN IF EXISTS fallback_message")
