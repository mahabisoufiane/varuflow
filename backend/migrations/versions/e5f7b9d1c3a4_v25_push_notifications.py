"""v25: device_tokens + push notification preferences

Revision ID: e5f7b9d1c3a4
Revises: d4f6a8c0e1b2
Create Date: 2026-04-22

Adds:
  * ``device_tokens`` — one row per installed mobile device per
    authenticated user. The raw Expo push token is persisted
    (unlike refresh tokens or magic links) because Expo's push API
    requires the full token on every send; revocation is handled by
    DELETEs when the user uninstalls or disables push.
  * Three preference booleans on ``organization_members``:
      - push_stockout_enabled
      - push_overdue_enabled
      - push_portal_order_enabled
    Preferences default to TRUE so new members get notified; users
    who want silence opt out from the mobile settings page.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e5f7b9d1c3a4"
down_revision = "d4f6a8c0e1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_tokens",
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
        # No FK here — user_id may be a Supabase auth.users UUID that
        # lives in a separate schema we don't own. The (org_id, user_id)
        # pair is enforced elsewhere via the tenant-scoped writes.
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("token", sa.String(length=255), nullable=False, unique=True),
        # "ios" / "android" / "huawei" — free-form string rather than an
        # enum because adding a new platform in the future shouldn't
        # require a schema migration.
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_device_tokens_org_user",
        "device_tokens",
        ["org_id", "user_id"],
    )

    for col in (
        "push_stockout_enabled",
        "push_overdue_enabled",
        "push_portal_order_enabled",
    ):
        op.add_column(
            "organization_members",
            sa.Column(col, sa.Boolean(), nullable=False, server_default=sa.true()),
        )


def downgrade() -> None:
    for col in (
        "push_portal_order_enabled",
        "push_overdue_enabled",
        "push_stockout_enabled",
    ):
        op.drop_column("organization_members", col)
    op.drop_index("ix_device_tokens_org_user", table_name="device_tokens")
    op.drop_table("device_tokens")
