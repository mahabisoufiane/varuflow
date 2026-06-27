"""route stop enhancements: POD, exceptions, notifications, scheduling.

Revision ID: oo6pp7qq8rr9
Revises: nn4oo5pp6qq7
Create Date: 2026-05-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "oo6pp7qq8rr9"
down_revision = "nn4oo5pp6qq7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # delivery_routes: add total_km and notification_threshold_minutes
    op.add_column("delivery_routes", sa.Column("total_km", sa.Numeric(10, 2), nullable=True))
    op.add_column(
        "delivery_routes",
        sa.Column("notification_threshold_minutes", sa.Integer(), nullable=False, server_default="15"),
    )

    # route_stops: add scheduled/completed timestamps
    op.add_column(
        "route_stops",
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "route_stops",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # route_stops: exception handling
    op.add_column("route_stops", sa.Column("exception_type", sa.String(50), nullable=True))
    op.add_column("route_stops", sa.Column("exception_reason", sa.Text(), nullable=True))
    op.add_column("route_stops", sa.Column("reschedule_date", sa.Date(), nullable=True))

    # route_stops: proof of delivery
    op.add_column("route_stops", sa.Column("pod_photo_url", sa.Text(), nullable=True))
    op.add_column(
        "route_stops",
        sa.Column("pod_signature_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("route_stops", "pod_signature_data")
    op.drop_column("route_stops", "pod_photo_url")
    op.drop_column("route_stops", "reschedule_date")
    op.drop_column("route_stops", "exception_reason")
    op.drop_column("route_stops", "exception_type")
    op.drop_column("route_stops", "completed_at")
    op.drop_column("route_stops", "scheduled_at")
    op.drop_column("delivery_routes", "notification_threshold_minutes")
    op.drop_column("delivery_routes", "total_km")
