"""v14: unique (org_id, user_id) on organization_members

Revision ID: f2a4c6e8d1b3
Revises: e1f3a5b7c9d2
Create Date: 2026-04-22

Prevents duplicate membership rows for the same user in the same org, which
used to be possible when:
  • a user double-clicked onboarding (creating two orgs)
  • an admin invited the same email twice under rare timing conditions

A user can still belong to multiple orgs (different org_id), but never twice
in the same org.
"""
from alembic import op

revision = "f2a4c6e8d1b3"
down_revision = "e1f3a5b7c9d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop any duplicate rows before adding the unique constraint so the
    # DDL does not fail on existing data. Keeps the earliest-created row.
    op.execute("""
        DELETE FROM organization_members a
        USING organization_members b
        WHERE a.org_id = b.org_id
          AND a.user_id = b.user_id
          AND a.created_at > b.created_at
    """)
    op.create_unique_constraint(
        "uq_organization_members_org_user",
        "organization_members",
        ["org_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_organization_members_org_user",
        "organization_members",
        type_="unique",
    )
