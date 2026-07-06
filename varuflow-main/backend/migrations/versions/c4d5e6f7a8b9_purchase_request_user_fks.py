"""purchase_requests: requested_by/reviewed_by are user ids, not staff FKs

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-07-06

`staff` is the bookings roster (no user linkage); pointing requested_by /
reviewed_by at it made every purchase-request INSERT violate the FK — the
feature never worked. The columns hold auth user ids; drop the FKs.
"""
from alembic import op

revision = "c4d5e6f7a8b9"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE purchase_requests DROP CONSTRAINT IF EXISTS purchase_requests_requested_by_fkey")
    op.execute("ALTER TABLE purchase_requests DROP CONSTRAINT IF EXISTS purchase_requests_reviewed_by_fkey")


def downgrade() -> None:
    op.execute("ALTER TABLE purchase_requests ADD CONSTRAINT purchase_requests_requested_by_fkey FOREIGN KEY (requested_by) REFERENCES staff(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE purchase_requests ADD CONSTRAINT purchase_requests_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES staff(id) ON DELETE SET NULL")
