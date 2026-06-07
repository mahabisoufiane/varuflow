"""Customer reviews router (Item 49).

Two surfaces:

* **Authenticated staff surface** (``/api/reviews/...``) — list,
  filter, export CSV, summary, and toggle ``is_public``.
* **Public magic-link surface** (``/api/reviews/submit/{token}``) —
  customer-facing endpoint with NO Supabase auth. Token hash lookup
  is the only credential; the state-machine lives in the service.

All state mutations go through :func:`log_action` so the audit log
is a complete record.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.reviews import Review, ReviewRequest
from app.services import review_service as svc
from app.services.audit import log_action
from app.middleware.plan_check import require_module


router = APIRouter(prefix="/api/reviews", tags=["reviews"], dependencies=[Depends(require_module("crm"))])


# ═══════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════


class ReviewOut(BaseModel):
    id: uuid.UUID
    rating: int
    comment: str | None
    is_public: bool
    source_type: str
    source_id: uuid.UUID
    customer_id: uuid.UUID | None
    created_at: datetime
    low: bool
    reasons: list[str]


class ReviewRequestOut(BaseModel):
    id: uuid.UUID
    source_type: str
    source_id: uuid.UUID
    customer_id: uuid.UUID | None
    sent_at: datetime
    responded_at: datetime | None
    expires_at: datetime


class ReviewSummaryOut(BaseModel):
    total: int
    average: float
    low_count: int
    histogram: dict[int, int]


class SubmitReviewIn(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)
    is_public: bool = False


class PublicReviewOut(BaseModel):
    """Public shape for the booking widget — no PII."""
    id: uuid.UUID
    rating: int
    comment: str | None
    created_at: datetime


class TogglePublicIn(BaseModel):
    is_public: bool


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _actor(ctx: tuple):
    user, _ = ctx
    return user.get("user_id")


def _to_review_out(r: Review) -> ReviewOut:
    # Re-derive low/reasons instead of storing — classify_movement-
    # style purity means tests can verify the mapping without a DB.
    flag = svc.classify_rating(r.rating, r.comment)
    # The source_type / source_id live on the request, not the
    # review; we fetch them eagerly at the query layer.
    source_type = getattr(r, "_source_type", "")
    source_id = getattr(r, "_source_id", None)
    return ReviewOut(
        id=r.id,
        rating=r.rating,
        comment=r.comment,
        is_public=r.is_public,
        source_type=source_type,
        source_id=source_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
        customer_id=r.customer_id,
        created_at=r.created_at,
        low=flag.low,
        reasons=list(flag.reasons),
    )


async def _attach_source(
    db: AsyncSession, org_id: uuid.UUID, reviews: list[Review]
) -> list[Review]:
    """Decorate each ``Review`` with ``_source_type`` / ``_source_id``
    pulled from its parent :class:`ReviewRequest` — single batched query."""
    if not reviews:
        return reviews
    ids = [r.request_id for r in reviews]
    rows = (
        await db.execute(
            select(ReviewRequest).where(
                ReviewRequest.org_id == org_id,
                ReviewRequest.id.in_(ids),
            )
        )
    ).scalars().all()
    by_id = {rr.id: rr for rr in rows}
    for r in reviews:
        rr = by_id.get(r.request_id)
        r._source_type = rr.source_type if rr else ""
        r._source_id = rr.source_id if rr else None
    return reviews


# ═══════════════════════════════════════════════════════════════════
# Public — customer magic-link submit
# ═══════════════════════════════════════════════════════════════════


@router.post("/submit/{token}", response_model=ReviewOut)
async def submit_review(
    token: str,
    body: SubmitReviewIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Submit a review via the emailed magic link.

    No Supabase auth — the token is the credential. Runs the full
    validation state machine: token must exist, must not be expired,
    must not already be responded to.
    """
    # Validate rating at the edge so a bad payload never reaches the DB.
    try:
        rating = svc.validate_rating(body.rating)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    token_hash = svc.hash_token(token)
    rr = (
        await db.execute(
            select(ReviewRequest).where(ReviewRequest.token_hash == token_hash)
        )
    ).scalar_one_or_none()
    if rr is None:
        # Generic error — don't leak whether the hash is unknown vs
        # expired vs already consumed.
        raise HTTPException(status_code=404, detail="Review link invalid or expired")
    if svc.is_token_expired(rr.expires_at):
        raise HTTPException(status_code=410, detail="Review link expired")
    if rr.responded_at is not None:
        raise HTTPException(status_code=409, detail="Review already submitted")

    # Duplicate-prevention belt-and-braces: the DB unique index on
    # reviews(request_id) enforces it too, but checking here gives a
    # clean 409 instead of an IntegrityError.
    existing = (
        await db.execute(select(Review).where(Review.request_id == rr.id))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Review already submitted")

    review = Review(
        request_id=rr.id,
        org_id=rr.org_id,
        customer_id=rr.customer_id,
        rating=rating,
        comment=(body.comment or None),
        is_public=bool(body.is_public),
    )
    rr.responded_at = datetime.now(timezone.utc)
    db.add(review)
    await db.flush()

    await log_action(
        db,
        action="review.submitted",
        org_id=rr.org_id,
        actor_user_id=None,
        target_type="review",
        target_id=str(review.id),
        request=request,
        extra={
            "request_id": str(rr.id),
            "rating": rating,
            "has_comment": bool(body.comment),
            "is_public": bool(body.is_public),
            "source_type": rr.source_type,
            "source_id": str(rr.source_id),
        },
    )
    await db.commit()
    await db.refresh(review)

    review._source_type = rr.source_type
    review._source_id = rr.source_id
    return _to_review_out(review)


# ═══════════════════════════════════════════════════════════════════
# Staff — list / summary / export / toggle
# ═══════════════════════════════════════════════════════════════════


@router.get("", response_model=list[ReviewOut])
async def list_reviews(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    low_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
):
    """Staff dashboard listing. ``low_only=true`` filters to ratings
    at or below :data:`svc.LOW_RATING_THRESHOLD` so ops can triage."""
    org_id = _org(ctx)
    q = select(Review).where(Review.org_id == org_id)
    if low_only:
        q = q.where(Review.rating <= svc.LOW_RATING_THRESHOLD)
    q = q.order_by(Review.created_at.desc()).limit(limit)
    reviews = (await db.execute(q)).scalars().all()
    await _attach_source(db, org_id, list(reviews))
    return [_to_review_out(r) for r in reviews]


@router.get("/summary", response_model=ReviewSummaryOut)
async def review_summary(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Histogram + average for the dashboard header."""
    org_id = _org(ctx)
    rows = (
        await db.execute(select(Review.rating).where(Review.org_id == org_id))
    ).scalars().all()
    summary = svc.summarise(list(rows))
    return ReviewSummaryOut(**summary.to_dict())


@router.get("/requests", response_model=list[ReviewRequestOut])
async def list_requests(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
):
    """Outbound-request listing. Useful for ops to see who hasn't
    responded yet."""
    org_id = _org(ctx)
    rows = (
        await db.execute(
            select(ReviewRequest)
            .where(ReviewRequest.org_id == org_id)
            .order_by(ReviewRequest.sent_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [
        ReviewRequestOut(
            id=rr.id,
            source_type=rr.source_type,
            source_id=rr.source_id,
            customer_id=rr.customer_id,
            sent_at=rr.sent_at,
            responded_at=rr.responded_at,
            expires_at=rr.expires_at,
        )
        for rr in rows
    ]


@router.get("/export.csv")
async def export_reviews_csv(
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Audited CSV export — staff download for compliance / analytics."""
    org_id = _org(ctx)
    q = (
        select(Review)
        .where(Review.org_id == org_id)
        .order_by(Review.created_at.desc())
        .limit(svc.EXPORT_ROW_CAP)
    )
    reviews = list((await db.execute(q)).scalars().all())
    await _attach_source(db, org_id, reviews)

    export_rows = [
        svc.ExportRow(
            created_at=r.created_at,
            rating=r.rating,
            comment=r.comment,
            is_public=r.is_public,
            source_type=getattr(r, "_source_type", "") or "",
            source_id=str(getattr(r, "_source_id", "") or ""),
            customer_id=str(r.customer_id) if r.customer_id else None,
            low_flag=svc.classify_rating(r.rating, r.comment).low,
        )
        for r in reviews
    ]
    body = svc.render_csv(export_rows)

    await log_action(
        db,
        action="review.exported",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="review",
        target_id=str(org_id),
        request=request,
        extra={"rows": len(export_rows)},
    )
    await db.commit()

    return Response(
        content=body,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="reviews.csv"',
        },
    )


@router.post("/{review_id}/public", response_model=ReviewOut)
async def toggle_public(
    review_id: uuid.UUID,
    body: TogglePublicIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Let staff show or hide a review on the public widget."""
    org_id = _org(ctx)
    review = await db.get(Review, review_id)
    if review is None or review.org_id != org_id:
        raise HTTPException(status_code=404, detail="review not found")
    review.is_public = bool(body.is_public)
    await db.flush()
    await log_action(
        db,
        action="review.public_toggled",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="review",
        target_id=str(review.id),
        request=request,
        extra={"is_public": review.is_public},
    )
    await db.commit()
    await _attach_source(db, org_id, [review])
    return _to_review_out(review)


# ═══════════════════════════════════════════════════════════════════
# Public widget — show approved reviews
# ═══════════════════════════════════════════════════════════════════


# Declared as its own router so the widget endpoint can live under
# ``/api/widget`` alongside the rest of the public embed surface.
public_router = APIRouter(prefix="/api/widget", tags=["widget"])


@public_router.get("/{slug}/reviews", response_model=list[PublicReviewOut])
async def widget_public_reviews(
    slug: str,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=50),
):
    """Show approved public reviews on the booking widget.

    Zero-PII shape — only rating, comment, and timestamp. The org is
    resolved from the slug so we never trust a client-supplied org_id.
    """
    from app.services.widget_service import resolve_org_by_slug

    org = await resolve_org_by_slug(db, slug=slug)
    if org is None:
        raise HTTPException(status_code=404, detail="org not found")

    rows = (
        await db.execute(
            select(Review)
            .where(Review.org_id == org.id, Review.is_public.is_(True))
            .order_by(Review.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [
        PublicReviewOut(
            id=r.id,
            rating=r.rating,
            comment=r.comment,
            created_at=r.created_at,
        )
        for r in rows
    ]
