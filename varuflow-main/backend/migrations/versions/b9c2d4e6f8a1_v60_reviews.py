"""v60 — Customer reviews and review requests (Item 49).

Two new tables:

* ``review_requests`` — one row per outbound review prompt tied to a
  completed booking (or an invoice, for future use). Stores a
  SHA-256 token hash so the public review form can be opened from a
  magic-link without Supabase auth. Response timestamp flips when a
  ``reviews`` row is created.
* ``reviews`` — the rating + optional comment the customer posted
  back. ``rating`` is constrained to 1..5 at the DB level so a
  buggy client can never persist a 0 or a 6. ``is_public`` controls
  whether the row surfaces on the public booking widget.

Spec asked for v52; v52 is taken by
``d0e1f2a3b4c5_v52_supplier_portal.py``. Following the same
convention used in §§58-§76 we land at the next free slot — v60
(chains from v59 developer keys).

Revision: b9c2d4e6f8a1
Revises:  a8b1c3d5e7f2 (v59 — developer keys, Item 45)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b9c2d4e6f8a1"
down_revision = "a8b1c3d5e7f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # ``SET NULL`` — if the customer is GDPR-erased we keep the
        # rating history (depersonalised) but drop the FK.
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # ``booking`` today, ``invoice`` reserved for post-purchase
        # flows. String (not enum) so extending doesn't need a DB
        # migration — the service layer keeps it honest.
        sa.Column("source_type", sa.String(length=16), nullable=False),
        # UUID of the source row (appointment.id or invoice.id). Not
        # a FK because it can refer to two different tables.
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        # SHA-256 hex digest of the raw magic-link token. Plaintext
        # is emailed to the customer once and never persisted.
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "responded_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        # Token TTL — 30 days matches the ShopBack / Trustpilot norm
        # and is short enough that stale links don't linger.
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_review_requests_org",
        "review_requests",
        ["org_id"],
    )
    # Magic-link lookup — the inbound endpoint hashes the raw token
    # and looks it up here. Unique so a (pathological) hash collision
    # can't silently grant access to another customer's request.
    op.create_index(
        "ix_review_requests_token_hash",
        "review_requests",
        ["token_hash"],
        unique=True,
    )
    # Duplicate-prevention lookup: "has a request already been sent
    # for this source?" Runs per completed booking, so it must be
    # fast.
    op.create_index(
        "ix_review_requests_source",
        "review_requests",
        ["org_id", "source_type", "source_id"],
    )

    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("review_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # DB-level 1..5 guard — client validation is not trusted.
        sa.Column(
            "rating",
            sa.Integer,
            nullable=False,
        ),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column(
            "is_public",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_reviews_rating_range"),
    )
    op.create_index("ix_reviews_org", "reviews", ["org_id"])
    # "Public reviews for this org" — the widget endpoint asks for
    # this exact shape.
    op.create_index(
        "ix_reviews_public",
        "reviews",
        ["org_id"],
        postgresql_where=sa.text("is_public = true"),
    )
    # One review per request — the duplicate-prevention invariant.
    op.create_index(
        "ix_reviews_request_unique",
        "reviews",
        ["request_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_reviews_request_unique", table_name="reviews")
    op.drop_index("ix_reviews_public", table_name="reviews")
    op.drop_index("ix_reviews_org", table_name="reviews")
    op.drop_table("reviews")
    op.drop_index("ix_review_requests_source", table_name="review_requests")
    op.drop_index("ix_review_requests_token_hash", table_name="review_requests")
    op.drop_index("ix_review_requests_org", table_name="review_requests")
    op.drop_table("review_requests")
