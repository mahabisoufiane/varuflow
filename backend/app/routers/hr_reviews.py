"""HR Performance reviews router: cycles and reviews."""
from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.bookings import Staff
from app.models.performance import PerformanceCycle, PerformanceReview

log = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_module("hr"))])

VALID_CYCLE_STATUSES = {"draft", "open", "closed"}
VALID_REVIEW_STATUSES = {"pending", "self_submitted", "reviewed", "completed"}


class CycleCreate(BaseModel):
    name: str
    start_date: date
    end_date: date
    status: str = "draft"
    cycle_frequency: str = "annual"  # quarterly | semi_annual | annual
    rating_labels: List[str] = [
        "Unsatisfactory", "Below Expectations", "Meets Expectations",
        "Exceeds Expectations", "Outstanding",
    ]


class CycleUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None
    cycle_frequency: Optional[str] = None
    rating_labels: Optional[List[str]] = None


class ReviewUpdate(BaseModel):
    goals: Optional[List[Any]] = None
    self_assessment: Optional[str] = None
    manager_review: Optional[str] = None
    overall_rating: Optional[int] = None
    status: Optional[str] = None
    reviewer_staff_id: Optional[uuid.UUID] = None
    check_in_notes: Optional[str] = None
    development_plan: Optional[List[Any]] = None


def _row(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


# ── Cycles ────────────────────────────────────────────────────────────────────

@router.get("/api/hr/performance-cycles")
async def list_cycles(
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        rows = (await db.execute(
            select(PerformanceCycle).where(PerformanceCycle.org_id == org_id)
            .order_by(PerformanceCycle.start_date.desc())
        )).scalars().all()
        return [_row(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_cycles failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/performance-cycles", status_code=201)
async def create_cycle(
    body: CycleCreate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        if body.status not in VALID_CYCLE_STATUSES:
            raise HTTPException(status_code=422, detail=f"Invalid status: {body.status}")
        row = PerformanceCycle(id=uuid.uuid4(), org_id=org_id, **body.model_dump())
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _row(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_cycle failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/hr/performance-cycles/{cycle_id}")
async def update_cycle(
    cycle_id: uuid.UUID,
    body: CycleUpdate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(PerformanceCycle).where(
                and_(PerformanceCycle.org_id == org_id, PerformanceCycle.id == cycle_id)
            )
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Cycle not found")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        await db.commit()
        await db.refresh(row)
        return _row(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"update_cycle failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/hr/performance-cycles/{cycle_id}", status_code=204)
async def delete_cycle(
    cycle_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(PerformanceCycle).where(
                and_(PerformanceCycle.org_id == org_id, PerformanceCycle.id == cycle_id)
            )
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Cycle not found")
        await db.delete(row)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"delete_cycle failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/performance-cycles/{cycle_id}/reviews", status_code=201)
async def bulk_create_reviews(
    cycle_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Create a PerformanceReview row for every staff member in the org (skip if one already exists)."""
    user, member = auth
    org_id = member.org_id
    try:
        cycle = (await db.execute(
            select(PerformanceCycle).where(
                and_(PerformanceCycle.org_id == org_id, PerformanceCycle.id == cycle_id)
            )
        )).scalar_one_or_none()
        if not cycle:
            raise HTTPException(status_code=404, detail="Cycle not found")

        all_staff = (await db.execute(
            select(Staff).where(Staff.org_id == org_id)
        )).scalars().all()

        existing = {
            str(r.staff_id)
            for r in (await db.execute(
                select(PerformanceReview).where(
                    and_(PerformanceReview.org_id == org_id, PerformanceReview.cycle_id == cycle_id)
                )
            )).scalars().all()
        }

        created = 0
        for s in all_staff:
            if str(s.id) not in existing:
                db.add(PerformanceReview(
                    id=uuid.uuid4(),
                    org_id=org_id,
                    cycle_id=cycle_id,
                    staff_id=s.id,
                ))
                created += 1

        await db.commit()
        return {"created": created}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"bulk_create_reviews failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Reviews ───────────────────────────────────────────────────────────────────

@router.get("/api/hr/performance-reviews")
async def list_reviews(
    cycle_id: Optional[uuid.UUID] = None,
    staff_id: Optional[uuid.UUID] = None,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        q = select(PerformanceReview).where(PerformanceReview.org_id == org_id)
        if cycle_id:
            q = q.where(PerformanceReview.cycle_id == cycle_id)
        if staff_id:
            q = q.where(PerformanceReview.staff_id == staff_id)
        rows = (await db.execute(q)).scalars().all()
        return [_row(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_reviews failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/hr/performance-reviews/{review_id}")
async def get_review(
    review_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(PerformanceReview).where(
                and_(PerformanceReview.org_id == org_id, PerformanceReview.id == review_id)
            )
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Review not found")
        return _row(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"get_review failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/hr/performance-reviews/{review_id}")
async def update_review(
    review_id: uuid.UUID,
    body: ReviewUpdate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(PerformanceReview).where(
                and_(PerformanceReview.org_id == org_id, PerformanceReview.id == review_id)
            )
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Review not found")
        if body.overall_rating is not None and not (1 <= body.overall_rating <= 5):
            raise HTTPException(status_code=422, detail="overall_rating must be 1–5")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        await db.commit()
        await db.refresh(row)
        return _row(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"update_review failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Calibration view ──────────────────────────────────────────────────────────

@router.get("/api/hr/performance-reviews/calibration")
async def calibration_view(
    cycle_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Side-by-side view of all reviews in a cycle: staff name + rating per goal."""
    user, member = auth
    org_id = member.org_id
    try:
        cycle = (await db.execute(
            select(PerformanceCycle).where(
                and_(PerformanceCycle.org_id == org_id, PerformanceCycle.id == cycle_id)
            )
        )).scalar_one_or_none()
        if not cycle:
            raise HTTPException(status_code=404, detail="Cycle not found")

        reviews = (await db.execute(
            select(PerformanceReview, Staff)
            .join(Staff, Staff.id == PerformanceReview.staff_id)
            .where(
                and_(PerformanceReview.org_id == org_id, PerformanceReview.cycle_id == cycle_id)
            )
            .order_by(Staff.name)
        )).all()

        return {
            "cycle": _row(cycle),
            "reviews": [
                {
                    **_row(rev),
                    "staff_name": staff.name,
                }
                for rev, staff in reviews
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"calibration_view failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Review PDF export ─────────────────────────────────────────────────────────

@router.get("/api/hr/performance-reviews/{review_id}/export-pdf", response_class=HTMLResponse)
async def export_review_pdf(
    review_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return a print-ready HTML view of the performance review (browser prints to PDF)."""
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(PerformanceReview, Staff)
            .join(Staff, Staff.id == PerformanceReview.staff_id)
            .where(and_(PerformanceReview.org_id == org_id, PerformanceReview.id == review_id))
        )).one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Review not found")

        review, staff = row
        cycle = (await db.execute(
            select(PerformanceCycle).where(PerformanceCycle.id == review.cycle_id)
        )).scalar_one_or_none()

        rating_labels = (cycle.rating_labels if cycle and cycle.rating_labels
                         else ["1","2","3","4","5"])

        def rating_label(r):
            if r is None:
                return "—"
            idx = int(r) - 1
            if 0 <= idx < len(rating_labels):
                return f"{r} – {rating_labels[idx]}"
            return str(r)

        goals_html = ""
        for i, g in enumerate(review.goals or [], 1):
            title = g.get("title", f"Goal {i}")
            target = g.get("target", "")
            self_r = rating_label(g.get("self_rating"))
            mgr_r = rating_label(g.get("manager_rating"))
            self_c = g.get("self_comment", "")
            mgr_c = g.get("manager_comment", "")
            goals_html += f"""
            <div class="goal">
              <h3>Goal {i}: {title}</h3>
              <p class="muted">Target: {target}</p>
              <table>
                <tr><th>Self-Rating</th><td>{self_r}</td>
                    <th>Manager Rating</th><td>{mgr_r}</td></tr>
              </table>
              {'<p><strong>Self comment:</strong> ' + self_c + '</p>' if self_c else ''}
              {'<p><strong>Manager comment:</strong> ' + mgr_c + '</p>' if mgr_c else ''}
            </div>"""

        dev_plan_html = ""
        for item in (review.development_plan or []):
            action = item.get("action", "")
            by = item.get("by_when", "")
            dev_plan_html += f"<li>{action}" + (f" <span class='muted'>— by {by}</span>" if by else "") + "</li>"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Performance Review — {staff.name}</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; color: #222; }}
    h1 {{ font-size: 22px; border-bottom: 2px solid #6366f1; padding-bottom: 8px; }}
    h2 {{ font-size: 16px; color: #6366f1; margin-top: 28px; }}
    h3 {{ font-size: 14px; margin-bottom: 4px; }}
    .goal {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin-bottom: 12px; }}
    .muted {{ color: #6b7280; font-size: 13px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 8px 0; }}
    th, td {{ border: 1px solid #e5e7eb; padding: 6px 10px; font-size: 13px; text-align: left; }}
    th {{ background: #f9fafb; }}
    .badge {{ display: inline-block; padding: 2px 10px; border-radius: 99px;
              font-size: 12px; background: #e0e7ff; color: #4338ca; }}
    @media print {{ body {{ margin: 20px; }} }}
  </style>
</head>
<body>
  <h1>Performance Review</h1>
  <table>
    <tr><th>Employee</th><td>{staff.name}</td>
        <th>Cycle</th><td>{cycle.name if cycle else '—'}</td></tr>
    <tr><th>Period</th><td>{cycle.start_date if cycle else '—'} – {cycle.end_date if cycle else '—'}</td>
        <th>Status</th><td><span class="badge">{review.status}</span></td></tr>
    <tr><th>Overall Rating</th><td colspan="3">{rating_label(review.overall_rating)}</td></tr>
  </table>

  <h2>Goals &amp; Ratings</h2>
  {goals_html or '<p class="muted">No goals recorded.</p>'}

  <h2>Self-Assessment</h2>
  <p>{review.self_assessment or '<span class="muted">Not submitted.</span>'}</p>

  <h2>Manager Review</h2>
  <p>{review.manager_review or '<span class="muted">Not completed.</span>'}</p>

  {'<h2>Mid-Cycle Check-In Notes</h2><p>' + review.check_in_notes + '</p>' if review.check_in_notes else ''}

  {('<h2>Development Plan</h2><ul>' + dev_plan_html + '</ul>') if dev_plan_html else ''}

  <p class="muted" style="margin-top:40px;border-top:1px solid #e5e7eb;padding-top:8px;">
    Generated by Varuflow · {review.updated_at.strftime('%Y-%m-%d') if review.updated_at else ''}
  </p>
  <script>window.print();</script>
</body>
</html>"""
        return HTMLResponse(content=html)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"export_review_pdf failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
