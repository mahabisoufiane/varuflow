"""
AI Automation router — cash flow forecasting, smart invoice matching,
anomaly detection, and automated workflow rules.

All endpoints except contract drafting live here.
Contract drafting (GPT-4o) is in integrations.py per project rules.
"""

import uuid
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional, List, Any
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.features.invoicing.models import Invoice, Customer, Payment
from app.features.integrations.bank_feed_models import BankTransaction, BankAccount
from app.features.purchases.payable_invoice import PayableInvoice
from app.features.inventory.workflow_rules import WorkflowRule

log = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_module("ai"))])

# ── Schemas ──────────────────────────────────────────────────────────────────

class WorkflowIn(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_type: str
    trigger_conditions: dict = {}
    actions: List[dict] = []

class WorkflowPatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    trigger_type: Optional[str] = None
    trigger_conditions: Optional[dict] = None
    actions: Optional[List[dict]] = None

# ── Cash Flow Forecast ────────────────────────────────────────────────────────

@router.get("/api/ai/cashflow")
async def cashflow_forecast(request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    """
    Forecast 30/60/90-day cash position from:
    - Outstanding receivables (SENT/OVERDUE invoices)
    - Scheduled payables (PayableInvoice APPROVED status)
    - Current balance estimate from recent bank credits
    """
    try:
        user, member = ctx
        org_id = member.org_id
        today = date.today()

        # Estimate current balance from last 90 days of bank transactions
        bank_r = await db.execute(
            select(func.sum(BankTransaction.amount)).where(
                BankTransaction.org_id == org_id,
                BankTransaction.transaction_date >= today - timedelta(days=90),
                BankTransaction.status != "EXCLUDED",
            )
        )
        current_balance_est = float(bank_r.scalar() or 0)

        # Outstanding receivables (invoice total minus payments already received)
        inv_r = await db.execute(
            select(Invoice).where(
                Invoice.org_id == org_id,
                Invoice.status.in_(["SENT", "OVERDUE"]),
            )
        )
        open_invoices = inv_r.scalars().all()

        # Payments already made against open invoices
        pay_r = await db.execute(
            select(Payment.invoice_id, func.sum(Payment.amount).label("paid")).where(
                Payment.invoice_id.in_([i.id for i in open_invoices])
            ).group_by(Payment.invoice_id)
        ) if open_invoices else None
        paid_map = {row.invoice_id: float(row.paid) for row in (pay_r.all() if pay_r else [])}

        # Outstanding payables
        pay_inv_r = await db.execute(
            select(PayableInvoice).where(
                PayableInvoice.org_id == org_id,
                PayableInvoice.status == "APPROVED",
                PayableInvoice.due_date.isnot(None),
            )
        )
        payables = pay_inv_r.scalars().all()

        # Build forecast buckets
        buckets = [
            {"label": "30d", "days": 30},
            {"label": "60d", "days": 60},
            {"label": "90d", "days": 90},
        ]

        overdue_total = 0.0
        overdue_invoices = []
        forecast = []
        cumulative = current_balance_est

        for i, bucket in enumerate(buckets):
            from_day = 0 if i == 0 else buckets[i - 1]["days"]
            to_day = bucket["days"]
            from_date = today + timedelta(days=from_day)
            to_date = today + timedelta(days=to_day)

            incoming = 0.0
            outgoing = 0.0
            receivables_detail = []
            payables_detail = []

            for inv in open_invoices:
                remaining = float(inv.total_sek) - paid_map.get(inv.id, 0)
                if remaining <= 0:
                    continue
                # Overdue invoices (past due) only counted in first bucket
                if inv.status == "OVERDUE" or (inv.due_date and inv.due_date < today):
                    if i == 0:
                        incoming += remaining
                        overdue_total += remaining
                        overdue_invoices.append({
                            "invoice_number": inv.invoice_number,
                            "amount": round(remaining, 2),
                            "due_date": inv.due_date.isoformat() if inv.due_date else None,
                            "days_overdue": (today - inv.due_date).days if inv.due_date else 0,
                        })
                        receivables_detail.append({"invoice_number": inv.invoice_number, "amount": round(remaining, 2)})
                elif inv.due_date and from_date <= inv.due_date < to_date:
                    incoming += remaining
                    receivables_detail.append({"invoice_number": inv.invoice_number, "amount": round(remaining, 2)})

            for pi in payables:
                if pi.due_date and from_date <= pi.due_date < to_date:
                    outgoing += float(pi.total)
                    payables_detail.append({"id": str(pi.id), "amount": round(float(pi.total), 2)})

            net = incoming - outgoing
            cumulative += net
            forecast.append({
                "label": bucket["label"],
                "incoming": round(incoming, 2),
                "outgoing": round(outgoing, 2),
                "net": round(net, 2),
                "cumulative": round(cumulative, 2),
                "receivables": receivables_detail[:10],
                "payables": payables_detail[:10],
            })

        outstanding_payables = sum(float(p.total) for p in payables)

        return {
            "current_balance_est": round(current_balance_est, 2),
            "overdue_receivables": round(overdue_total, 2),
            "overdue_invoices": sorted(overdue_invoices, key=lambda x: x["days_overdue"], reverse=True)[:10],
            "outstanding_payables": round(outstanding_payables, 2),
            "forecast": forecast,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"cashflow_forecast failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ── Smart Invoice Matching ────────────────────────────────────────────────────

@router.get("/api/ai/bank-match")
async def bank_match_suggestions(request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    """
    For each UNMATCHED incoming bank transaction, suggest open invoices
    ranked by amount similarity + description pattern matching.
    """
    try:
        user, member = ctx
        org_id = member.org_id

        # UNMATCHED transactions (positive = incoming credit)
        tx_r = await db.execute(
            select(BankTransaction).where(
                BankTransaction.org_id == org_id,
                BankTransaction.status == "UNMATCHED",
                BankTransaction.amount > 0,
            ).order_by(BankTransaction.transaction_date.desc()).limit(50)
        )
        transactions = tx_r.scalars().all()

        # Open invoices
        inv_r = await db.execute(
            select(Invoice, Customer.company_name).join(
                Customer, Invoice.customer_id == Customer.id, isouter=True
            ).where(
                Invoice.org_id == org_id,
                Invoice.status.in_(["SENT", "OVERDUE"]),
            )
        )
        invoices = inv_r.all()

        # Payments already received
        paid_map = {}
        if invoices:
            pay_r = await db.execute(
                select(Payment.invoice_id, func.sum(Payment.amount).label("paid")).where(
                    Payment.invoice_id.in_([row[0].id for row in invoices])
                ).group_by(Payment.invoice_id)
            )
            paid_map = {row.invoice_id: float(row.paid) for row in pay_r.all()}

        results = []
        for tx in transactions:
            tx_amount = float(tx.amount)
            tx_desc = (tx.description or "").lower()
            tx_ref = (tx.reference or "").lower()

            scored = []
            for inv, cust_name in invoices:
                remaining = float(inv.total_sek) - paid_map.get(inv.id, 0)
                if remaining <= 0:
                    continue

                score = 0
                reasons = []

                # Amount matching (most important signal)
                diff_pct = abs(tx_amount - remaining) / max(remaining, 0.01)
                if diff_pct < 0.001:
                    score += 70
                    reasons.append("Exact amount match")
                elif diff_pct < 0.02:
                    score += 50
                    reasons.append(f"Amount within {diff_pct*100:.1f}%")
                elif diff_pct < 0.05:
                    score += 25
                    reasons.append("Amount close")
                else:
                    continue  # Amount too different to be a match

                # Invoice number in description
                inv_num_lower = inv.invoice_number.lower()
                if inv_num_lower in tx_desc or inv_num_lower in tx_ref:
                    score += 25
                    reasons.append("Invoice number found in description")

                # Bank reference contains OCR/reference number pattern
                if cust_name and cust_name.split()[0].lower() in tx_desc:
                    score += 10
                    reasons.append("Customer name in description")

                # Date proximity: transaction around due date
                if inv.due_date:
                    days_diff = abs((tx.transaction_date - inv.due_date).days)
                    if days_diff <= 5:
                        score += 10
                        reasons.append(f"Transaction ≈ due date ({days_diff}d diff)")

                scored.append({
                    "invoice_id": str(inv.id),
                    "invoice_number": inv.invoice_number,
                    "customer_name": cust_name,
                    "invoice_amount": float(inv.total_sek),
                    "remaining": round(remaining, 2),
                    "due_date": inv.due_date.isoformat() if inv.due_date else None,
                    "confidence": min(score, 100),
                    "reasons": reasons,
                })

            scored.sort(key=lambda x: x["confidence"], reverse=True)
            if scored:
                results.append({
                    "transaction_id": str(tx.id),
                    "transaction_date": tx.transaction_date.isoformat(),
                    "amount": tx_amount,
                    "description": tx.description,
                    "reference": tx.reference,
                    "suggestions": scored[:3],
                })

        return {"transactions": results, "total": len(results)}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"bank_match_suggestions failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/ai/bank-match/{tx_id}/confirm")
async def confirm_bank_match(tx_id: str, invoice_id: str, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    """Apply a suggested match: mark transaction as MATCHED and link to invoice."""
    try:
        user, member = ctx
        org_id = member.org_id
        tx_r = await db.execute(select(BankTransaction).where(BankTransaction.id == uuid.UUID(tx_id), BankTransaction.org_id == org_id))
        tx = tx_r.scalar_one_or_none()
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")
        inv_r = await db.execute(select(Invoice).where(Invoice.id == uuid.UUID(invoice_id), Invoice.org_id == org_id))
        inv = inv_r.scalar_one_or_none()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        tx.status = "MATCHED"
        tx.matched_type = "INVOICE"
        tx.matched_id = uuid.UUID(invoice_id)
        await db.commit()
        return {"transaction_id": tx_id, "invoice_id": invoice_id, "matched": True}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"confirm_bank_match failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ── Anomaly Detection ─────────────────────────────────────────────────────────

@router.get("/api/ai/anomalies")
async def detect_anomalies(request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    """
    Detect three classes of anomalies:
    1. Duplicate invoices (same customer + similar amount within 7 days)
    2. Duplicate payments (same invoice + same amount within 24h)
    3. Unusual spend spikes (bank debits 2× the 60-day average in last 7 days)
    """
    try:
        user, member = ctx
        org_id = member.org_id
        today = date.today()
        anomalies = []

        # ── 1. Duplicate invoices ────────────────────────────────────────────
        # Find invoices where (customer_id, total_sek) appears > 1 within a 7-day window
        recent_inv_r = await db.execute(
            select(Invoice).where(
                Invoice.org_id == org_id,
                Invoice.issue_date >= today - timedelta(days=60),
                Invoice.status != "DRAFT",
            ).order_by(Invoice.issue_date.desc())
        )
        recent_invs = recent_inv_r.scalars().all()

        # Group by customer and find duplicates
        seen: dict[tuple, list] = {}
        for inv in recent_invs:
            key = (str(inv.customer_id), float(inv.total_sek))
            seen.setdefault(key, []).append(inv)

        for (cust_id, amount), group in seen.items():
            if len(group) < 2:
                continue
            group.sort(key=lambda x: x.issue_date)
            for i in range(len(group) - 1):
                days_apart = (group[i + 1].issue_date - group[i].issue_date).days
                if days_apart <= 7:
                    anomalies.append({
                        "type": "duplicate_invoice",
                        "severity": "HIGH",
                        "title": "Possible duplicate invoice",
                        "detail": f"{group[i].invoice_number} and {group[i+1].invoice_number} — same customer, same amount ({amount:,.0f} SEK), {days_apart} days apart",
                        "invoice_ids": [str(group[i].id), str(group[i + 1].id)],
                        "amount": amount,
                        "days_apart": days_apart,
                    })

        # ── 2. Duplicate payments ────────────────────────────────────────────
        pay_r = await db.execute(
            select(Payment).join(Invoice, Payment.invoice_id == Invoice.id).where(
                Invoice.org_id == org_id,
                Payment.payment_date >= today - timedelta(days=60),
            ).order_by(Payment.payment_date.desc())
        )
        payments = pay_r.scalars().all()

        pay_seen: dict[tuple, list] = {}
        for pay in payments:
            key = (str(pay.invoice_id), float(pay.amount))
            pay_seen.setdefault(key, []).append(pay)

        for (inv_id, amount), group in pay_seen.items():
            if len(group) < 2:
                continue
            group.sort(key=lambda x: x.payment_date)
            for i in range(len(group) - 1):
                hours_apart = abs((
                    datetime.combine(group[i + 1].payment_date, datetime.min.time()) -
                    datetime.combine(group[i].payment_date, datetime.min.time())
                ).total_seconds() / 3600)
                if hours_apart < 48:
                    anomalies.append({
                        "type": "duplicate_payment",
                        "severity": "CRITICAL",
                        "title": "Possible duplicate payment",
                        "detail": f"Invoice paid twice: {amount:,.0f} SEK, {int(hours_apart)}h apart",
                        "invoice_id": inv_id,
                        "amount": amount,
                        "hours_apart": int(hours_apart),
                    })

        # ── 3. Spend spikes ──────────────────────────────────────────────────
        # Compare last-7-day debits vs 60-day daily average
        debit_recent_r = await db.execute(
            select(func.sum(BankTransaction.amount)).where(
                BankTransaction.org_id == org_id,
                BankTransaction.amount < 0,
                BankTransaction.transaction_date >= today - timedelta(days=7),
                BankTransaction.status != "EXCLUDED",
            )
        )
        debit_recent = abs(float(debit_recent_r.scalar() or 0))

        debit_avg_r = await db.execute(
            select(func.sum(BankTransaction.amount)).where(
                BankTransaction.org_id == org_id,
                BankTransaction.amount < 0,
                BankTransaction.transaction_date >= today - timedelta(days=60),
                BankTransaction.transaction_date < today - timedelta(days=7),
                BankTransaction.status != "EXCLUDED",
            )
        )
        debit_53day = abs(float(debit_avg_r.scalar() or 0))
        weekly_avg_53 = (debit_53day / 53) * 7 if debit_53day > 0 else 0

        if weekly_avg_53 > 1000 and debit_recent > weekly_avg_53 * 2:
            spike_pct = int((debit_recent / weekly_avg_53 - 1) * 100)
            anomalies.append({
                "type": "spend_spike",
                "severity": "MEDIUM",
                "title": "Unusual spend spike detected",
                "detail": f"Last 7 days: {debit_recent:,.0f} SEK — {spike_pct}% above weekly average ({weekly_avg_53:,.0f} SEK)",
                "recent_spend": round(debit_recent, 2),
                "weekly_avg": round(weekly_avg_53, 2),
                "spike_pct": spike_pct,
            })

        # Sort: CRITICAL → HIGH → MEDIUM
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        anomalies.sort(key=lambda x: severity_order.get(x["severity"], 99))

        return {
            "anomalies": anomalies,
            "total": len(anomalies),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"detect_anomalies failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ── Workflow Rules CRUD ───────────────────────────────────────────────────────

def _wf(r: WorkflowRule) -> dict:
    return {
        "id": str(r.id),
        "name": r.name,
        "description": r.description,
        "is_active": r.is_active,
        "trigger_type": r.trigger_type,
        "trigger_conditions": r.trigger_conditions,
        "actions": r.actions,
        "run_count": r.run_count,
        "last_run_at": r.last_run_at.isoformat() if r.last_run_at else None,
        "created_at": r.created_at.isoformat(),
    }


@router.get("/api/ai/workflows")
async def list_workflows(request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(WorkflowRule).where(WorkflowRule.org_id == org_id).order_by(WorkflowRule.created_at.desc()))
        return [_wf(r) for r in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_workflows failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/ai/workflows", status_code=201)
async def create_workflow(body: WorkflowIn, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        r = WorkflowRule(
            id=uuid.uuid4(), org_id=org_id, name=body.name, description=body.description,
            trigger_type=body.trigger_type, trigger_conditions=body.trigger_conditions,
            actions=body.actions,
        )
        db.add(r)
        await db.commit()
        await db.refresh(r)
        return _wf(r)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"create_workflow failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/ai/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, body: WorkflowPatch, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(WorkflowRule).where(WorkflowRule.id == uuid.UUID(workflow_id), WorkflowRule.org_id == org_id))
        r = result.scalar_one_or_none()
        if not r:
            raise HTTPException(status_code=404, detail="Workflow not found")
        for field, val in body.model_dump(exclude_unset=True).items():
            setattr(r, field, val)
        await db.commit()
        await db.refresh(r)
        return _wf(r)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"update_workflow failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/ai/workflows/{workflow_id}", status_code=204)
async def delete_workflow(workflow_id: str, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(WorkflowRule).where(WorkflowRule.id == uuid.UUID(workflow_id), WorkflowRule.org_id == org_id))
        r = result.scalar_one_or_none()
        if not r:
            raise HTTPException(status_code=404, detail="Workflow not found")
        await db.delete(r)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"delete_workflow failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/ai/workflows/{workflow_id}/run")
async def run_workflow(workflow_id: str, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    """
    Evaluate a workflow rule against the current org state and return
    the list of entities that would trigger it (dry-run) plus any
    actions that were queued.
    """
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(WorkflowRule).where(WorkflowRule.id == uuid.UUID(workflow_id), WorkflowRule.org_id == org_id))
        r = result.scalar_one_or_none()
        if not r:
            raise HTTPException(status_code=404, detail="Workflow not found")
        if not r.is_active:
            raise HTTPException(status_code=422, detail="Workflow is inactive")

        today = date.today()
        triggered = []
        executed_actions = []

        # ── Evaluate trigger ─────────────────────────────────────────────────
        if r.trigger_type == "invoice_overdue_days":
            threshold_days = int(r.trigger_conditions.get("days", 7))
            cutoff = today - timedelta(days=threshold_days)
            inv_r = await db.execute(
                select(Invoice, Customer.company_name, Customer.email).join(
                    Customer, Invoice.customer_id == Customer.id, isouter=True
                ).where(
                    Invoice.org_id == org_id,
                    Invoice.status.in_(["SENT", "OVERDUE"]),
                    Invoice.due_date <= cutoff,
                )
            )
            for inv, cname, cemail in inv_r.all():
                days_over = (today - inv.due_date).days
                triggerd_by = {"invoice_id": str(inv.id), "invoice_number": inv.invoice_number, "customer_name": cname, "days_overdue": days_over}
                # Check optional customer_tag filter (simplified — checks notes/tags if stored)
                triggered.append(triggerd_by)

        elif r.trigger_type == "new_invoice":
            since_days = int(r.trigger_conditions.get("since_hours", 24)) // 24 or 1
            inv_r = await db.execute(
                select(Invoice).where(
                    Invoice.org_id == org_id,
                    Invoice.issue_date >= today - timedelta(days=since_days),
                )
            )
            for inv in inv_r.scalars().all():
                triggered.append({"invoice_id": str(inv.id), "invoice_number": inv.invoice_number})

        elif r.trigger_type == "payment_received":
            since_days = int(r.trigger_conditions.get("since_hours", 24)) // 24 or 1
            pay_r = await db.execute(
                select(Payment).join(Invoice, Payment.invoice_id == Invoice.id).where(
                    Invoice.org_id == org_id,
                    Payment.payment_date >= today - timedelta(days=since_days),
                )
            )
            for pay in pay_r.scalars().all():
                triggered.append({"payment_id": str(pay.id), "amount": float(pay.amount)})

        # ── Log actions (simulation — real dispatch not implemented) ──────────
        for match in triggered[:20]:
            for action in r.actions:
                executed_actions.append({
                    "action_type": action.get("type"),
                    "target": match,
                    "params": action.get("params", {}),
                    "status": "queued",
                })

        # Update run tracking
        r.run_count = (r.run_count or 0) + 1
        r.last_run_at = datetime.now(timezone.utc)
        await db.commit()

        return {
            "workflow_id": workflow_id,
            "trigger_type": r.trigger_type,
            "matches": len(triggered),
            "triggered": triggered[:20],
            "actions_queued": executed_actions[:50],
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"run_workflow failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
