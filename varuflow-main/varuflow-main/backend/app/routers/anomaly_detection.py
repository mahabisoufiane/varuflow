"""Anomaly Detection router.

Scans financial and operational data for outliers and flags them
in the anomaly_findings table. Supports review, dismiss, and escalate.
"""
import logging
import math
import uuid
from datetime import date, timedelta
from statistics import mean, stdev
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.anomaly import AnomalyFinding
from app.models.expenses import Expense
from app.models.inventory import PurchaseOrder, PurchaseOrderItem
from app.models.invoicing import Customer, Invoice, Payment

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/anomalies", tags=["anomaly-detection"])


# ── Scanner helpers ───────────────────────────────────────────────────────────

async def _scan_duplicate_invoices(org_id: uuid.UUID, db: AsyncSession) -> list[dict]:
    """Same customer + same amount within ±30 days."""
    cutoff = date.today() - timedelta(days=180)
    result = await db.execute(
        select(Invoice)
        .where(Invoice.org_id == org_id, Invoice.issue_date >= cutoff)
        .order_by(Invoice.customer_id, Invoice.total_sek, Invoice.issue_date)
    )
    invoices = result.scalars().all()
    findings = []
    for i in range(len(invoices) - 1):
        a, b = invoices[i], invoices[i + 1]
        if (a.customer_id == b.customer_id
                and abs(float(a.total_sek) - float(b.total_sek)) < 0.01
                and abs((b.issue_date - a.issue_date).days) <= 30
                and a.id != b.id):
            findings.append({
                "type": "duplicate_invoice",
                "severity": "high",
                "title": f"Possible duplicate invoice: {float(a.total_sek):.2f} for same customer",
                "detail": f"Invoice {a.invoice_number} and {b.invoice_number} have the same amount and customer within 30 days.",
                "context": {"invoice_ids": [str(a.id), str(b.id)], "amount": float(a.total_sek), "customer_id": str(a.customer_id)},
            })
    return findings


async def _scan_duplicate_payments(org_id: uuid.UUID, db: AsyncSession) -> list[dict]:
    """Same customer + same amount within 7 days."""
    cutoff = date.today() - timedelta(days=90)
    result = await db.execute(
        select(Payment, Invoice.customer_id)
        .join(Invoice, Invoice.id == Payment.invoice_id)
        .where(Payment.org_id == org_id, Payment.payment_date >= cutoff)
        .order_by(Invoice.customer_id, Payment.amount, Payment.payment_date)
    )
    rows = result.all()
    findings = []
    for i in range(len(rows) - 1):
        pa, ca = rows[i]
        pb, cb = rows[i + 1]
        if (ca == cb
                and abs(float(pa.amount) - float(pb.amount)) < 0.01
                and abs((pb.payment_date - pa.payment_date).days) <= 7
                and pa.id != pb.id):
            findings.append({
                "type": "duplicate_payment",
                "severity": "high",
                "title": f"Possible duplicate payment: {float(pa.amount):.2f}",
                "detail": f"Two payments of the same amount from the same customer within 7 days.",
                "context": {"payment_ids": [str(pa.id), str(pb.id)], "amount": float(pa.amount), "customer_id": str(ca)},
            })
    return findings


async def _scan_unusual_expenses(org_id: uuid.UUID, db: AsyncSession) -> list[dict]:
    """Expense > mean + 2 * std for its category."""
    result = await db.execute(
        select(Expense)
        .where(Expense.org_id == org_id, Expense.deleted_at.is_(None))
        .order_by(Expense.category_id, Expense.amount)
    )
    expenses = result.scalars().all()

    by_cat: dict[str, list] = {}
    for e in expenses:
        key = str(e.category_id) if e.category_id else "uncategorized"
        by_cat.setdefault(key, []).append(e)

    findings = []
    for cat, items in by_cat.items():
        if len(items) < 5:
            continue
        amounts = [float(e.amount) for e in items]
        mu = mean(amounts)
        sd = stdev(amounts)
        threshold = mu + 2 * sd
        for e in items:
            if float(e.amount) > threshold:
                findings.append({
                    "type": "unusual_expense",
                    "severity": "medium",
                    "title": f"Unusual expense: {float(e.amount):.2f} (category avg {mu:.2f})",
                    "detail": f"This expense is more than 2 standard deviations above the category mean.",
                    "context": {"expense_id": str(e.id), "amount": float(e.amount), "category_avg": round(mu, 2), "category_std": round(sd, 2)},
                })
    return findings


async def _scan_supplier_price_spikes(org_id: uuid.UUID, db: AsyncSession) -> list[dict]:
    """Product purchased at > mean + 2 std of last 3 purchases."""
    result = await db.execute(
        select(PurchaseOrderItem, PurchaseOrder.supplier_id)
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.purchase_order_id)
        .where(PurchaseOrder.org_id == org_id)
        .order_by(PurchaseOrderItem.product_id, PurchaseOrder.created_at.desc())
    )
    rows = result.all()

    # Group by (supplier_id, product_id) → last N prices
    history: dict[tuple, list] = {}
    for item, supplier_id in rows:
        key = (str(supplier_id), str(item.product_id))
        history.setdefault(key, []).append((item, float(item.unit_price)))

    findings = []
    for (supplier_id, product_id), entries in history.items():
        if len(entries) < 4:
            continue
        # Most recent entry vs baseline of the 3 before it
        recent_item, recent_price = entries[0]
        baseline_prices = [p for _, p in entries[1:4]]
        baseline_mean = mean(baseline_prices)
        if baseline_mean > 0:
            pct_increase = (recent_price - baseline_mean) / baseline_mean * 100
            if pct_increase > 25:
                findings.append({
                    "type": "supplier_price_spike",
                    "severity": "medium" if pct_increase < 50 else "high",
                    "title": f"Supplier price spike: +{pct_increase:.0f}% above typical",
                    "detail": f"Latest unit price {recent_price:.2f} vs avg {baseline_mean:.2f} for the same product.",
                    "context": {"product_id": product_id, "supplier_id": supplier_id,
                                "latest_price": recent_price, "baseline_avg": round(baseline_mean, 2),
                                "pct_increase": round(pct_increase, 1)},
                })
    return findings


async def _scan_payment_behavior_change(org_id: uuid.UUID, db: AsyncSession) -> list[dict]:
    """Customer who usually pays in N days is now significantly later."""
    cutoff_12m = date.today() - timedelta(days=365)
    cutoff_90d = date.today() - timedelta(days=90)
    result = await db.execute(
        select(Invoice.customer_id, Invoice.due_date, Payment.payment_date)
        .join(Payment, Payment.invoice_id == Invoice.id)
        .where(Invoice.org_id == org_id, Invoice.issue_date >= cutoff_12m, Invoice.status == "paid")
    )
    rows = result.all()

    by_customer: dict[str, list[tuple]] = {}
    for customer_id, due_date, payment_date in rows:
        by_customer.setdefault(str(customer_id), []).append((due_date, payment_date))

    findings = []
    for cid, entries in by_customer.items():
        if len(entries) < 5:
            continue
        all_delays = [(pd - dd).days for dd, pd in entries]
        historical = all_delays[:-3]
        recent = all_delays[-3:]
        if not historical:
            continue
        hist_avg = mean(historical)
        recent_avg = mean(recent)
        if recent_avg > hist_avg + 20 and recent_avg > 30:
            findings.append({
                "type": "payment_behavior_change",
                "severity": "medium",
                "title": f"Customer payment delay increased: avg {recent_avg:.0f} days (was {hist_avg:.0f})",
                "detail": f"Recent 3 payments averaged {recent_avg:.0f} days late, historically {hist_avg:.0f} days.",
                "context": {"customer_id": cid, "historical_avg_days": round(hist_avg, 1), "recent_avg_days": round(recent_avg, 1)},
            })
    return findings


async def _run_full_scan(org_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> int:
    """Run all detectors and persist new findings. Returns count of new findings."""
    all_findings: list[dict] = []
    all_findings += await _scan_duplicate_invoices(org_id, db)
    all_findings += await _scan_duplicate_payments(org_id, db)
    all_findings += await _scan_unusual_expenses(org_id, db)
    all_findings += await _scan_supplier_price_spikes(org_id, db)
    all_findings += await _scan_payment_behavior_change(org_id, db)

    count = 0
    for f in all_findings:
        db.add(AnomalyFinding(
            id=uuid.uuid4(),
            org_id=org_id,
            anomaly_type=f["type"],
            severity=f["severity"],
            title=f["title"],
            detail=f.get("detail"),
            context=f.get("context"),
        ))
        count += 1
    await db.commit()
    return count


# ── Schemas ───────────────────────────────────────────────────────────────────

class ResolveIn(BaseModel):
    status: str  # dismissed | escalated
    resolution_note: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/scan")
async def trigger_scan(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a full anomaly scan. Returns count of new findings."""
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        user_id = uuid.UUID(str(member["user_id"]))
        count = await _run_full_scan(org_id, user_id, db)
        return {"new_findings": count}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"anomaly scan failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("")
async def list_findings(
    status: Optional[str] = Query(None),
    anomaly_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        q = select(AnomalyFinding).where(AnomalyFinding.org_id == org_id)
        if status:
            q = q.where(AnomalyFinding.status == status)
        if anomaly_type:
            q = q.where(AnomalyFinding.anomaly_type == anomaly_type)
        if severity:
            q = q.where(AnomalyFinding.severity == severity)

        count_q = select(func.count()).select_from(q.subquery())
        total = (await db.execute(count_q)).scalar() or 0

        result = await db.execute(q.order_by(AnomalyFinding.detected_at.desc()).limit(limit).offset(offset))
        findings = result.scalars().all()
        return {
            "total": total,
            "items": [
                {"id": str(f.id), "anomaly_type": f.anomaly_type, "severity": f.severity,
                 "title": f.title, "detail": f.detail, "context": f.context,
                 "status": f.status, "detected_at": f.detected_at.isoformat(),
                 "resolved_at": f.resolved_at.isoformat() if f.resolved_at else None}
                for f in findings
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_anomalies failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/summary")
async def anomaly_summary(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Count by status and severity for the dashboard card."""
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        result = await db.execute(
            select(AnomalyFinding.status, AnomalyFinding.severity, func.count(AnomalyFinding.id))
            .where(AnomalyFinding.org_id == org_id)
            .group_by(AnomalyFinding.status, AnomalyFinding.severity)
        )
        rows = result.all()
        return {"breakdown": [{"status": r[0], "severity": r[1], "count": r[2]} for r in rows]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"anomaly_summary failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{finding_id}")
async def resolve_finding(
    finding_id: uuid.UUID,
    body: ResolveIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        finding = await db.get(AnomalyFinding, finding_id)
        if not finding or finding.org_id != org_id:
            raise HTTPException(status_code=404, detail="Finding not found")
        if body.status not in ("dismissed", "escalated"):
            raise HTTPException(status_code=422, detail="status must be dismissed or escalated")
        from datetime import datetime, timezone
        finding.status = body.status
        finding.resolved_at = datetime.now(tz=timezone.utc)
        finding.resolved_by = uuid.UUID(str(member["user_id"]))
        finding.resolution_note = body.resolution_note
        await db.commit()
        return {"id": str(finding.id), "status": finding.status}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"resolve_finding failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")
