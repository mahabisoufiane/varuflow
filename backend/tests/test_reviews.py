"""Tests for customer reviews (Item 49).

Pure + source-contract style, matching Items 28-47.

Required test names (spec):

* test_review_request_sent_after_booking
* test_customer_submits_review
* test_rating_stored_correctly
* test_low_rating_flagged
* test_public_review_shown_on_widget
* test_token_expiry
* test_duplicate_review_prevented
* test_export_csv
* test_staff_review_dashboard
* test_org_isolation
"""
from __future__ import annotations

import csv
import io
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

from app.services import review_service as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"


def _read(relpath: str) -> str:
    return (_BACKEND_ROOT / relpath).read_text()


ROUTER_SRC = _read("routers/reviews.py")
SERVICE_SRC = _read("services/review_service.py")
DISPATCH_SRC = _read("services/review_dispatch.py")
MODEL_SRC = _read("models/reviews.py")
BOOKINGS_SRC = _read("routers/bookings.py")
SCHEDULER_SRC = _read("services/scheduler.py")
MAIN_SRC = _read("main.py")

_MIGRATIONS_DIR = _BACKEND_ROOT.parent / "migrations" / "versions"
_V60 = _MIGRATIONS_DIR / "b9c2d4e6f8a1_v60_reviews.py"
MIGRATION_SRC = _V60.read_text() if _V60.exists() else ""


# ═══════════════════════════════════════════════════════════════════
# 1. test_review_request_sent_after_booking
# ═══════════════════════════════════════════════════════════════════


def test_review_request_sent_after_booking():
    # bookings.set_appointment_status hooks review request creation
    # on the completion branch.
    assert 'if body.status == "completed" and appt.customer_id is not None:' in BOOKINGS_SRC
    assert "maybe_create_review_request" in BOOKINGS_SRC
    assert 'source_type="booking"' in BOOKINGS_SRC
    # Dispatch helper is tenant-scoped and idempotent.
    assert "async def maybe_create_review_request" in DISPATCH_SRC
    assert "ReviewRequest.org_id == org_id" in DISPATCH_SRC
    assert "ReviewRequest.source_type == source_type" in DISPATCH_SRC


# ═══════════════════════════════════════════════════════════════════
# 2. test_customer_submits_review
# ═══════════════════════════════════════════════════════════════════


def test_customer_submits_review():
    # Public magic-link submit endpoint — NO get_current_member guard
    # on this specific route (token is the credential).
    assert '@router.post("/submit/{token}", response_model=ReviewOut)' in ROUTER_SRC
    assert "async def submit_review" in ROUTER_SRC
    # Token hash lookup — raw token never compared directly.
    assert "svc.hash_token(token)" in ROUTER_SRC
    assert "ReviewRequest.token_hash == token_hash" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 3. test_rating_stored_correctly
# ═══════════════════════════════════════════════════════════════════


def test_rating_stored_correctly():
    # Pure validator enforces 1..5 bound.
    assert svc.validate_rating(1) == 1
    assert svc.validate_rating(5) == 5
    with pytest.raises(ValueError):
        svc.validate_rating(0)
    with pytest.raises(ValueError):
        svc.validate_rating(6)
    with pytest.raises(ValueError):
        svc.validate_rating("abc")  # type: ignore[arg-type]
    # DB-level CHECK constraint in the migration belt-and-braces.
    assert "rating >= 1 AND rating <= 5" in MIGRATION_SRC
    # Model includes the same CheckConstraint so ORM-driven inserts
    # get the guard too.
    assert 'CheckConstraint("rating >= 1 AND rating <= 5"' in MODEL_SRC


# ═══════════════════════════════════════════════════════════════════
# 4. test_low_rating_flagged
# ═══════════════════════════════════════════════════════════════════


def test_low_rating_flagged():
    # Threshold is 3 stars — at/below is low.
    assert svc.LOW_RATING_THRESHOLD == 3
    assert svc.classify_rating(1).low is True
    assert svc.classify_rating(3).low is True
    assert svc.classify_rating(4).low is False
    assert svc.classify_rating(5).low is False
    # Comment adds a follow-up reason when the rating is already low.
    flag = svc.classify_rating(2, "terrible experience")
    assert "low_rating" in flag.reasons
    assert "low_rating_with_comment" in flag.reasons
    # 4-star with a comment is NOT flagged.
    assert svc.classify_rating(4, "pretty good").low is False
    # Router exposes a low_only filter.
    assert "low_only: bool = Query(default=False)" in ROUTER_SRC
    assert "Review.rating <= svc.LOW_RATING_THRESHOLD" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 5. test_public_review_shown_on_widget
# ═══════════════════════════════════════════════════════════════════


def test_public_review_shown_on_widget():
    # Widget endpoint — no auth, org resolved from slug.
    assert 'public_router = APIRouter(prefix="/api/widget"' in ROUTER_SRC
    assert '@public_router.get("/{slug}/reviews", response_model=list[PublicReviewOut])' in ROUTER_SRC
    assert "Review.is_public.is_(True)" in ROUTER_SRC
    # Zero-PII output — no customer_id on the public shape.
    assert "class PublicReviewOut(BaseModel):" in ROUTER_SRC
    # Partial index exists on (org_id) WHERE is_public=true for
    # fast widget scans.
    assert "ix_reviews_public" in MIGRATION_SRC


# ═══════════════════════════════════════════════════════════════════
# 6. test_token_expiry
# ═══════════════════════════════════════════════════════════════════


def test_token_expiry():
    # TTL matches the spec (30 days).
    assert svc.REVIEW_TOKEN_TTL_DAYS == 30
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    expiry = svc.compute_expiry(now)
    assert expiry == now + timedelta(days=30)
    # Past-expiry check is timezone-safe.
    assert svc.is_token_expired(now - timedelta(seconds=1), now=now) is True
    assert svc.is_token_expired(now + timedelta(days=1), now=now) is False
    # Naive datetime is coerced to UTC so a buggy caller can't fake
    # "not expired" by passing a naive value.
    naive = datetime(2020, 1, 1)
    assert svc.is_token_expired(naive, now=now) is True
    # Router returns 410 on expired token.
    assert 'status_code=410, detail="Review link expired"' in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 7. test_duplicate_review_prevented
# ═══════════════════════════════════════════════════════════════════


def test_duplicate_review_prevented():
    # Router short-circuits when responded_at is set.
    assert "if rr.responded_at is not None:" in ROUTER_SRC
    assert 'status_code=409, detail="Review already submitted"' in ROUTER_SRC
    # Belt-and-braces DB check.
    assert "select(Review).where(Review.request_id == rr.id)" in ROUTER_SRC
    # Migration unique index enforces it at the DB layer.
    assert "ix_reviews_request_unique" in MIGRATION_SRC
    assert "unique=True" in MIGRATION_SRC
    # Dispatch helper is idempotent — returns None on second call.
    assert "if existing is not None:" in DISPATCH_SRC
    assert "return None" in DISPATCH_SRC


# ═══════════════════════════════════════════════════════════════════
# 8. test_export_csv
# ═══════════════════════════════════════════════════════════════════


def test_export_csv():
    assert '@router.get("/export.csv")' in ROUTER_SRC
    assert "svc.render_csv" in ROUTER_SRC
    assert 'media_type="text/csv"' in ROUTER_SRC
    assert 'attachment; filename="reviews.csv"' in ROUTER_SRC
    # Audited export.
    assert '"review.exported"' in ROUTER_SRC

    # Pure round-trip
    row = svc.ExportRow(
        created_at=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        rating=5,
        comment="great",
        is_public=True,
        source_type="booking",
        source_id="abc",
        customer_id="cust-1",
        low_flag=False,
    )
    body = svc.render_csv([row])
    parsed = list(csv.reader(io.StringIO(body)))
    assert parsed[0] == list(svc.CSV_HEADERS)
    assert parsed[1][1] == "5"
    assert parsed[1][2] == "great"
    assert parsed[1][3] == "yes"  # is_public

    # Commas and quotes escape cleanly.
    row2 = svc.ExportRow(
        created_at=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        rating=1,
        comment='Service was "bad", refund now',
        is_public=False,
        source_type="booking",
        source_id="abc",
        customer_id=None,
        low_flag=True,
    )
    body2 = svc.render_csv([row2])
    parsed2 = list(csv.reader(io.StringIO(body2)))
    assert parsed2[1][2] == 'Service was "bad", refund now'


# ═══════════════════════════════════════════════════════════════════
# 9. test_staff_review_dashboard
# ═══════════════════════════════════════════════════════════════════


def test_staff_review_dashboard():
    # Staff listing endpoint — authed, tenant-scoped, newest first.
    assert '@router.get("", response_model=list[ReviewOut])' in ROUTER_SRC
    assert "ctx: tuple = Depends(get_current_member)" in ROUTER_SRC
    assert "Review.org_id == org_id" in ROUTER_SRC
    assert "order_by(Review.created_at.desc())" in ROUTER_SRC
    # Summary endpoint exposes histogram + average.
    assert '@router.get("/summary", response_model=ReviewSummaryOut)' in ROUTER_SRC
    # Pure summariser backs the summary endpoint.
    summary = svc.summarise([5, 5, 4, 3, 1])
    assert summary.total == 5
    assert summary.average == 3.6
    assert summary.low_count == 2  # 3 and 1
    assert summary.histogram == {1: 1, 2: 0, 3: 1, 4: 1, 5: 2}
    # Requests listing for ops triage.
    assert '@router.get("/requests", response_model=list[ReviewRequestOut])' in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 10. test_org_isolation
# ═══════════════════════════════════════════════════════════════════


def test_org_isolation():
    # Every authed query filters by org_id — never trust client input.
    assert "Review.org_id == org_id" in ROUTER_SRC
    assert "def _org(ctx:" in ROUTER_SRC
    assert "org_id = _org(ctx)" in ROUTER_SRC
    # Toggle-public guard checks both object existence AND org match.
    assert "review.org_id != org_id" in ROUTER_SRC
    # Widget public path resolves org from slug, never from client.
    assert "resolve_org_by_slug(db, slug=slug)" in ROUTER_SRC
    # Dispatch helper is also tenant-scoped.
    assert "ReviewRequest.org_id == org_id" in DISPATCH_SRC


# ═══════════════════════════════════════════════════════════════════
# Invariants
# ═══════════════════════════════════════════════════════════════════


def test_router_registered_in_main():
    assert "reviews" in MAIN_SRC
    assert "app.include_router(reviews.router)" in MAIN_SRC
    assert "app.include_router(reviews.public_router)" in MAIN_SRC


def test_migration_chains_from_v59():
    assert 'revision = "b9c2d4e6f8a1"' in MIGRATION_SRC
    assert 'down_revision = "a8b1c3d5e7f2"' in MIGRATION_SRC
    # Both tables created.
    assert 'op.create_table(\n        "review_requests"' in MIGRATION_SRC
    assert 'op.create_table(\n        "reviews"' in MIGRATION_SRC


def test_token_helpers_pure():
    # Deterministic hash — same input → same output.
    raw = "alpha-bravo-charlie"
    assert svc.hash_token(raw) == svc.hash_token(raw)
    # Different inputs → different hashes.
    assert svc.hash_token("a") != svc.hash_token("b")
    # Hash is 64-char hex (SHA-256).
    h = svc.hash_token(raw)
    assert len(h) == 64
    int(h, 16)  # valid hex
    # Empty input rejected.
    with pytest.raises(ValueError):
        svc.hash_token("")
    # Generated tokens are unique.
    t1 = svc.generate_token()
    t2 = svc.generate_token()
    assert t1 != t2
    assert len(t1) >= 40  # urlsafe(32) is 43 chars


def test_log_action_on_mutations():
    # Every mutating endpoint calls log_action.
    assert '"review.submitted"' in ROUTER_SRC
    assert '"review.exported"' in ROUTER_SRC
    assert '"review.public_toggled"' in ROUTER_SRC


def test_scheduler_job_registered():
    # Sweep job is wired in with its own advisory lock.
    assert "_LOCK_REVIEW_REQUEST_SWEEP" in SCHEDULER_SRC
    assert "async def _review_request_sweep" in SCHEDULER_SRC
    assert 'id="review_request_sweep"' in SCHEDULER_SRC
    # Cron — daily 04:00 Stockholm.
    assert 'CronTrigger(hour=4, minute=0, timezone="Europe/Stockholm")' in SCHEDULER_SRC


def test_summarise_empty_list():
    # Edge case — no ratings → zero average, zero-filled histogram.
    summary = svc.summarise([])
    assert summary.total == 0
    assert summary.average == 0.0
    assert summary.low_count == 0
    assert summary.histogram == {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}


def test_summarise_ignores_out_of_range():
    # Defense in depth — a polluted DB column shouldn't crash the
    # summariser.
    summary = svc.summarise([5, 0, 6, "bad", None, 3])  # type: ignore[list-item]
    assert summary.total == 2
    assert summary.histogram[5] == 1
    assert summary.histogram[3] == 1
