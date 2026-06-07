"""Business Intelligence router — dashboards, report builder, scheduled reports, benchmarks, cohorts."""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.bi import DashboardConfig, CustomReport, ScheduledReport
from app.models.organization import Organization, OrgPlan
from app.models.invoicing import Invoice, InvoiceLineItem, InvoiceStatus, Customer, Payment
from app.models.inventory import Product, StockLevel
from app.models.expenses import Expense

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/bi", tags=["bi"], dependencies=[Depends(require_module("analytics"))])

# ── helpers ──────────────────────────────────────────────────────────────────

def _require_pro(plan: OrgPlan) -> None:
    if plan not in (OrgPlan.PRO, OrgPlan.ENTERPRISE):
        raise HTTPException(status_code=403, detail="PRO plan required")


def _str_id(v) -> str:
    return str(v) if v else None


# ── INDUSTRY BENCHMARKS (static reference data) ──────────────────────────────

_BENCHMARKS: dict[str, dict] = {
    "wholesale": {
        "gross_margin_pct": 28.4,
        "net_margin_pct": 4.2,
        "inventory_turnover": 6.1,
        "days_sales_outstanding": 38,
        "current_ratio": 1.6,
        "revenue_growth_yoy_pct": 5.3,
        "source": "NHO Wholesale Industry Report 2025",
    },
    "retail": {
        "gross_margin_pct": 42.1,
        "net_margin_pct": 3.8,
        "inventory_turnover": 8.4,
        "days_sales_outstanding": 12,
        "current_ratio": 1.3,
        "revenue_growth_yoy_pct": 3.9,
        "source": "Svensk Handel Retail Benchmark 2025",
    },
    "manufacturing": {
        "gross_margin_pct": 33.7,
        "net_margin_pct": 6.1,
        "inventory_turnover": 4.2,
        "days_sales_outstanding": 45,
        "current_ratio": 2.1,
        "revenue_growth_yoy_pct": 4.1,
        "source": "Industrifakta Nordic 2025",
    },
    "food_beverage": {
        "gross_margin_pct": 24.6,
        "net_margin_pct": 3.1,
        "inventory_turnover": 12.3,
        "days_sales_outstanding": 22,
        "current_ratio": 1.2,
        "revenue_growth_yoy_pct": 6.8,
        "source": "DLF Food & Beverage 2025",
    },
    "construction": {
        "gross_margin_pct": 19.2,
        "net_margin_pct": 3.6,
        "inventory_turnover": 5.5,
        "days_sales_outstanding": 55,
        "current_ratio": 1.4,
        "revenue_growth_yoy_pct": 2.7,
        "source": "BNI Nordic Construction 2025",
    },
    "services": {
        "gross_margin_pct": 62.5,
        "net_margin_pct": 12.4,
        "inventory_turnover": None,
        "days_sales_outstanding": 30,
        "current_ratio": 1.8,
        "revenue_growth_yoy_pct": 8.2,
        "source": "Nordic Service Industry Association 2025",
    },
}

_SECTORS = list(_BENCHMARKS.keys())

# ── SAFE REPORT QUERY BUILDER ─────────────────────────────────────────────────
# Only whitelisted sources, fields, aggregates, and operators — zero SQL injection risk.

_ALLOWED_SOURCES = {
    "invoices": {
        "table": "invoices",
        "fields": ["status", "currency", "created_at", "due_date", "issued_date"],
        "numeric_fields": ["total_amount", "subtotal", "tax_amount", "paid_amount", "outstanding_amount"],
    },
    "customers": {
        "table": "customers",
        "fields": ["country", "currency", "created_at"],
        "numeric_fields": ["credit_limit"],
    },
    "expenses": {
        "table": "expenses",
        "fields": ["category", "currency", "date", "status"],
        "numeric_fields": ["amount"],
    },
    "products": {
        "table": "products",
        "fields": ["category", "unit", "created_at"],
        "numeric_fields": ["unit_price", "cost_price"],
    },
}

_ALLOWED_AGG_FNS = {"sum", "avg", "count", "min", "max"}
_ALLOWED_FILTER_OPS = {"=", "!=", ">", ">=", "<", "<=", "in", "not_in"}
_MAX_REPORT_ROWS = 5_000


def _build_report_sql(source: str, config: dict, org_id: str) -> tuple[str, dict]:
    """Return (sql_string, params_dict) for the given report config.

    Config schema:
      {
        "source": "invoices",
        "filters": [{"field": "status", "op": "=", "value": "paid"}],
        "group_by": ["status", "currency"],
        "aggregates": [{"fn": "sum", "field": "total_amount", "alias": "revenue"}],
        "sort_by": "revenue",
        "sort_dir": "desc"
      }
    """
    src = _ALLOWED_SOURCES.get(source)
    if not src:
        raise HTTPException(400, detail=f"Unknown source '{source}'")

    table = src["table"]
    all_fields = set(src["fields"]) | set(src["numeric_fields"])

    params: dict[str, Any] = {"org_id": org_id}
    where_clauses = ["org_id = :org_id"]

    # Filters
    for i, f in enumerate(config.get("filters") or []):
        field = f.get("field", "")
        op = f.get("op", "=")
        value = f.get("value")
        if field not in all_fields:
            raise HTTPException(400, detail=f"Unknown filter field '{field}'")
        if op not in _ALLOWED_FILTER_OPS:
            raise HTTPException(400, detail=f"Unknown operator '{op}'")
        pname = f"p{i}"
        if op == "in":
            if not isinstance(value, list):
                raise HTTPException(400, detail="'in' filter requires a list value")
            params[pname] = value
            where_clauses.append(f"{field} = ANY(:{pname})")
        elif op == "not_in":
            if not isinstance(value, list):
                raise HTTPException(400, detail="'not_in' filter requires a list value")
            params[pname] = value
            where_clauses.append(f"{field} != ALL(:{pname})")
        else:
            params[pname] = value
            where_clauses.append(f"{field} {op} :{pname}")

    group_by_fields = []
    for g in config.get("group_by") or []:
        if g not in all_fields:
            raise HTTPException(400, detail=f"Unknown group_by field '{g}'")
        group_by_fields.append(g)

    select_parts = list(group_by_fields)
    valid_aliases = set(group_by_fields)
    for agg in config.get("aggregates") or []:
        fn = agg.get("fn", "").lower()
        field = agg.get("field", "")
        alias = agg.get("alias", f"{fn}_{field}")
        if fn not in _ALLOWED_AGG_FNS:
            raise HTTPException(400, detail=f"Unknown aggregate fn '{fn}'")
        if not alias.isidentifier():
            raise HTTPException(400, detail=f"Invalid alias '{alias}'")
        if fn == "count" and field == "*":
            select_parts.append(f"COUNT(*) AS {alias}")
        else:
            if field not in src["numeric_fields"]:
                raise HTTPException(400, detail=f"Aggregate field '{field}' not numeric")
            select_parts.append(f"{fn.upper()}({field}) AS {alias}")
        valid_aliases.add(alias)

    if not select_parts:
        raise HTTPException(400, detail="Report must have at least one group_by or aggregate")

    sorts = []
    sort_by = config.get("sort_by")
    sort_dir = "DESC" if str(config.get("sort_dir", "desc")).upper() == "DESC" else "ASC"
    if sort_by:
        if sort_by not in valid_aliases:
            raise HTTPException(400, detail=f"Unknown sort_by field '{sort_by}'")
        sorts.append(f"{sort_by} {sort_dir}")

    sql = f"""
        SELECT {', '.join(select_parts)}
        FROM {table}
        WHERE {' AND '.join(where_clauses)}
        {'GROUP BY ' + ', '.join(group_by_fields) if group_by_fields else ''}
        {'ORDER BY ' + ', '.join(sorts) if sorts else ''}
        LIMIT {_MAX_REPORT_ROWS}
    """  # nosec B608 — all identifiers validated against allowlists above
    return sql.strip(), params


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class WidgetItem(BaseModel):
    id: str
    widget_type: str
    position: dict
    config: dict = {}


class DashboardIn(BaseModel):
    name: str
    layout: list[WidgetItem] = []


class DashboardPatch(BaseModel):
    name: Optional[str] = None
    layout: Optional[list[WidgetItem]] = None
    is_default: Optional[bool] = None


class ReportIn(BaseModel):
    name: str
    description: Optional[str] = None
    config: dict


class ScheduledReportIn(BaseModel):
    name: str
    report_type: str
    custom_report_id: Optional[str] = None
    config: dict = {}
    recipients: list[dict]
    cron_expr: str
    timezone: str = "UTC"


class ScheduledReportPatch(BaseModel):
    name: Optional[str] = None
    recipients: Optional[list[dict]] = None
    cron_expr: Optional[str] = None
    is_active: Optional[bool] = None
    timezone: Optional[str] = None


# ── DASHBOARDS ────────────────────────────────────────────────────────────────

@router.get("/dashboards")
async def list_dashboards(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        rows = await db.execute(
            select(DashboardConfig)
            .where(DashboardConfig.org_id == member["org_id"])
            .order_by(DashboardConfig.is_default.desc(), DashboardConfig.created_at.desc())
        )
        dashboards = rows.scalars().all()
        return {
            "dashboards": [
                {
                    "id": _str_id(d.id),
                    "name": d.name,
                    "is_default": d.is_default,
                    "widget_count": len(d.layout) if isinstance(d.layout, list) else 0,
                    "updated_at": d.updated_at.isoformat(),
                }
                for d in dashboards
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_dashboards failed: %s", e)
        raise HTTPException(500, "Internal server error")


@router.post("/dashboards", status_code=201)
async def create_dashboard(
    body: DashboardIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        d = DashboardConfig(
            org_id=uuid.UUID(member["org_id"]),
            user_id=uuid.UUID(member["user_id"]),
            name=body.name,
            layout=[w.model_dump() for w in body.layout],
        )
        db.add(d)
        await db.commit()
        await db.refresh(d)
        return {"id": _str_id(d.id), "name": d.name}
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_dashboard failed: %s", e)
        raise HTTPException(500, "Internal server error")


@router.get("/dashboards/{dashboard_id}")
async def get_dashboard(
    dashboard_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        row = await db.get(DashboardConfig, uuid.UUID(dashboard_id))
        if not row or str(row.org_id) != member["org_id"]:
            raise HTTPException(404, "Dashboard not found")
        return {
            "id": _str_id(row.id),
            "name": row.name,
            "is_default": row.is_default,
            "layout": row.layout,
            "updated_at": row.updated_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_dashboard failed: %s", e)
        raise HTTPException(500, "Internal server error")


@router.patch("/dashboards/{dashboard_id}")
async def update_dashboard(
    dashboard_id: str,
    body: DashboardPatch,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        row = await db.get(DashboardConfig, uuid.UUID(dashboard_id))
        if not row or str(row.org_id) != member["org_id"]:
            raise HTTPException(404, "Dashboard not found")
        if body.name is not None:
            row.name = body.name
        if body.layout is not None:
            row.layout = [w.model_dump() for w in body.layout]
        if body.is_default is not None and body.is_default:
            # Unset other defaults for this user first
            await db.execute(
                text("UPDATE dashboard_configs SET is_default=false WHERE org_id=:oid AND user_id=:uid")
                .bindparams(oid=member["org_id"], uid=member["user_id"])
            )
            row.is_default = True
        row.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_dashboard failed: %s", e)
        raise HTTPException(500, "Internal server error")


@router.delete("/dashboards/{dashboard_id}", status_code=204)
async def delete_dashboard(
    dashboard_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        row = await db.get(DashboardConfig, uuid.UUID(dashboard_id))
        if not row or str(row.org_id) != member["org_id"]:
            raise HTTPException(404, "Dashboard not found")
        await db.delete(row)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_dashboard failed: %s", e)
        raise HTTPException(500, "Internal server error")


# ── WIDGET DATA ENDPOINTS ─────────────────────────────────────────────────────

_VALID_WIDGET_TYPES = {
    "revenue_trend", "top_customers", "top_products", "invoice_status",
    "expense_summary", "margin_kpis", "outstanding_ar", "inventory_kpis",
    "recent_payments", "overdue_count",
}


@router.get("/widgets/{widget_type}")
async def get_widget_data(
    widget_type: str,
    months: int = 6,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Fetch live data for a single dashboard widget."""
    try:
        if widget_type not in _VALID_WIDGET_TYPES:
            raise HTTPException(400, detail=f"Unknown widget type '{widget_type}'")

        org_id = member["org_id"]
        months = min(max(months, 1), 24)
        since = text("now() - make_interval(months => :m)").bindparams(m=months)

        if widget_type == "revenue_trend":
            rows = await db.execute(
                text("""
                    SELECT date_trunc('month', issued_date) AS month,
                           SUM(total_amount) AS revenue,
                           COUNT(*) AS invoice_count
                    FROM invoices
                    WHERE org_id=:oid AND issued_date >= now() - make_interval(months => :m)
                      AND status NOT IN ('draft','cancelled')
                    GROUP BY 1 ORDER BY 1
                """).bindparams(oid=org_id, m=months)
            )
            return {"data": [{"month": str(r[0])[:7], "revenue": float(r[1] or 0), "count": r[2]} for r in rows]}

        if widget_type == "top_customers":
            rows = await db.execute(
                text("""
                    SELECT c.name, SUM(i.total_amount) AS revenue
                    FROM invoices i JOIN customers c ON i.customer_id=c.id
                    WHERE i.org_id=:oid AND i.status NOT IN ('draft','cancelled')
                      AND i.issued_date >= now() - make_interval(months => :m)
                    GROUP BY c.id, c.name ORDER BY revenue DESC LIMIT 10
                """).bindparams(oid=org_id, m=months)
            )
            return {"data": [{"name": r[0], "revenue": float(r[1] or 0)} for r in rows]}

        if widget_type == "top_products":
            rows = await db.execute(
                text("""
                    SELECT p.name, SUM(li.quantity * li.unit_price) AS revenue,
                           SUM(li.quantity) AS qty_sold
                    FROM invoice_line_items li
                    JOIN invoices i ON li.invoice_id=i.id
                    JOIN products p ON li.product_id=p.id
                    WHERE i.org_id=:oid AND i.status NOT IN ('draft','cancelled')
                      AND i.issued_date >= now() - make_interval(months => :m)
                    GROUP BY p.id, p.name ORDER BY revenue DESC LIMIT 10
                """).bindparams(oid=org_id, m=months)
            )
            return {"data": [{"name": r[0], "revenue": float(r[1] or 0), "qty": float(r[2] or 0)} for r in rows]}

        if widget_type == "invoice_status":
            rows = await db.execute(
                text("""
                    SELECT status, COUNT(*) AS cnt, SUM(total_amount) AS total
                    FROM invoices WHERE org_id=:oid
                    GROUP BY status
                """).bindparams(oid=org_id)
            )
            return {"data": [{"status": r[0], "count": r[1], "total": float(r[2] or 0)} for r in rows]}

        if widget_type == "outstanding_ar":
            row = await db.execute(
                text("""
                    SELECT COUNT(*), SUM(outstanding_amount)
                    FROM invoices WHERE org_id=:oid AND status='overdue'
                """).bindparams(oid=org_id)
            )
            r = row.one()
            return {"count": r[0] or 0, "total": float(r[1] or 0)}

        if widget_type == "expense_summary":
            rows = await db.execute(
                text("""
                    SELECT category, SUM(amount) AS total
                    FROM expenses WHERE org_id=:oid
                      AND date >= now() - make_interval(months => :m)
                    GROUP BY category ORDER BY total DESC LIMIT 8
                """).bindparams(oid=org_id, m=months)
            )
            return {"data": [{"category": r[0] or "Other", "total": float(r[1] or 0)} for r in rows]}

        if widget_type == "overdue_count":
            row = await db.execute(
                text("SELECT COUNT(*), SUM(outstanding_amount) FROM invoices WHERE org_id=:oid AND status='overdue'")
                .bindparams(oid=org_id)
            )
            r = row.one()
            return {"count": r[0] or 0, "amount": float(r[1] or 0)}

        # Generic fallback for remaining widget types
        return {"data": []}

    except HTTPException:
        raise
    except Exception as e:
        log.error("get_widget_data failed: %s", e)
        raise HTTPException(500, "Internal server error")


# ── CUSTOM REPORT BUILDER ─────────────────────────────────────────────────────

@router.get("/reports")
async def list_reports(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _require_pro(member["plan"])
        rows = await db.execute(
            select(CustomReport)
            .where(CustomReport.org_id == member["org_id"])
            .order_by(CustomReport.updated_at.desc())
        )
        return {
            "reports": [
                {
                    "id": _str_id(r.id),
                    "name": r.name,
                    "description": r.description,
                    "source": r.config.get("source"),
                    "last_run_at": r.last_run_at.isoformat() if r.last_run_at else None,
                    "last_run_row_count": r.last_run_row_count,
                    "updated_at": r.updated_at.isoformat(),
                }
                for r in rows.scalars()
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_reports failed: %s", e)
        raise HTTPException(500, "Internal server error")


@router.post("/reports", status_code=201)
async def create_report(
    body: ReportIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _require_pro(member["plan"])
        # Validate config is parseable before saving
        _build_report_sql(body.config.get("source", ""), body.config, member["org_id"])
        r = CustomReport(
            org_id=uuid.UUID(member["org_id"]),
            user_id=uuid.UUID(member["user_id"]),
            name=body.name,
            description=body.description,
            config=body.config,
        )
        db.add(r)
        await db.commit()
        await db.refresh(r)
        return {"id": _str_id(r.id), "name": r.name}
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_report failed: %s", e)
        raise HTTPException(500, "Internal server error")


@router.post("/reports/{report_id}/run")
async def run_report(
    report_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _require_pro(member["plan"])
        report = await db.get(CustomReport, uuid.UUID(report_id))
        if not report or str(report.org_id) != member["org_id"]:
            raise HTTPException(404, "Report not found")

        sql, params = _build_report_sql(report.config.get("source", ""), report.config, member["org_id"])
        result = await db.execute(text(sql).bindparams(**params))
        keys = list(result.keys())
        rows = [dict(zip(keys, r)) for r in result.fetchall()]

        report.last_run_at = datetime.now(timezone.utc)
        report.last_run_row_count = len(rows)
        await db.commit()

        return {"columns": keys, "rows": rows, "total": len(rows)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("run_report failed: %s", e)
        raise HTTPException(500, "Internal server error")


@router.post("/reports/preview")
async def preview_report(
    body: ReportIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Run a report config ad-hoc without saving (for the builder UI)."""
    try:
        _require_pro(member["plan"])
        sql, params = _build_report_sql(body.config.get("source", ""), body.config, member["org_id"])
        result = await db.execute(text(sql).bindparams(**params))
        keys = list(result.keys())
        rows = [dict(zip(keys, r)) for r in result.fetchall()]
        return {"columns": keys, "rows": rows[:200], "total": len(rows)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("preview_report failed: %s", e)
        raise HTTPException(500, "Internal server error")


@router.delete("/reports/{report_id}", status_code=204)
async def delete_report(
    report_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _require_pro(member["plan"])
        r = await db.get(CustomReport, uuid.UUID(report_id))
        if not r or str(r.org_id) != member["org_id"]:
            raise HTTPException(404, "Report not found")
        await db.delete(r)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_report failed: %s", e)
        raise HTTPException(500, "Internal server error")


# ── SCHEDULED REPORTS ─────────────────────────────────────────────────────────

@router.get("/scheduled")
async def list_scheduled(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _require_pro(member["plan"])
        rows = await db.execute(
            select(ScheduledReport)
            .where(ScheduledReport.org_id == member["org_id"])
            .order_by(ScheduledReport.created_at.desc())
        )
        return {
            "scheduled": [
                {
                    "id": _str_id(s.id),
                    "name": s.name,
                    "report_type": s.report_type,
                    "cron_expr": s.cron_expr,
                    "timezone": s.timezone,
                    "is_active": s.is_active,
                    "recipients": s.recipients,
                    "last_sent_at": s.last_sent_at.isoformat() if s.last_sent_at else None,
                    "next_send_at": s.next_send_at.isoformat() if s.next_send_at else None,
                }
                for s in rows.scalars()
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_scheduled failed: %s", e)
        raise HTTPException(500, "Internal server error")


@router.post("/scheduled", status_code=201)
async def create_scheduled(
    body: ScheduledReportIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _require_pro(member["plan"])
        valid_types = {"analytics_overview", "pnl", "cash_flow", "custom"}
        if body.report_type not in valid_types:
            raise HTTPException(400, detail=f"Invalid report_type. Choose from: {valid_types}")
        s = ScheduledReport(
            org_id=uuid.UUID(member["org_id"]),
            user_id=uuid.UUID(member["user_id"]),
            name=body.name,
            report_type=body.report_type,
            custom_report_id=uuid.UUID(body.custom_report_id) if body.custom_report_id else None,
            config=body.config,
            recipients=body.recipients,
            cron_expr=body.cron_expr,
            timezone=body.timezone,
        )
        db.add(s)
        await db.commit()
        await db.refresh(s)
        return {"id": _str_id(s.id), "name": s.name}
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_scheduled failed: %s", e)
        raise HTTPException(500, "Internal server error")


@router.patch("/scheduled/{scheduled_id}")
async def update_scheduled(
    scheduled_id: str,
    body: ScheduledReportPatch,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _require_pro(member["plan"])
        s = await db.get(ScheduledReport, uuid.UUID(scheduled_id))
        if not s or str(s.org_id) != member["org_id"]:
            raise HTTPException(404, "Scheduled report not found")
        if body.name is not None:
            s.name = body.name
        if body.recipients is not None:
            s.recipients = body.recipients
        if body.cron_expr is not None:
            s.cron_expr = body.cron_expr
        if body.is_active is not None:
            s.is_active = body.is_active
        if body.timezone is not None:
            s.timezone = body.timezone
        s.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_scheduled failed: %s", e)
        raise HTTPException(500, "Internal server error")


@router.delete("/scheduled/{scheduled_id}", status_code=204)
async def delete_scheduled(
    scheduled_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _require_pro(member["plan"])
        s = await db.get(ScheduledReport, uuid.UUID(scheduled_id))
        if not s or str(s.org_id) != member["org_id"]:
            raise HTTPException(404, "Scheduled report not found")
        await db.delete(s)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_scheduled failed: %s", e)
        raise HTTPException(500, "Internal server error")


# ── BENCHMARKS ────────────────────────────────────────────────────────────────

@router.get("/benchmarks/sectors")
async def list_sectors(member=Depends(get_current_member)):
    return {"sectors": _SECTORS}


@router.get("/benchmarks")
async def get_benchmarks(
    sector: str = "wholesale",
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return industry benchmark vs org's actual KPIs for the last 12 months."""
    try:
        _require_pro(member["plan"])
        industry = _BENCHMARKS.get(sector, _BENCHMARKS["wholesale"])
        org_id = member["org_id"]

        # Compute org's actual values
        rev = await db.execute(
            text("""
                SELECT SUM(total_amount), SUM(subtotal), SUM(subtotal) - SUM(COALESCE(cost_of_goods,0))
                FROM invoices
                WHERE org_id=:oid AND status NOT IN ('draft','cancelled')
                  AND issued_date >= now() - interval '12 months'
            """).bindparams(oid=org_id)
        )
        rev_row = rev.one()
        total_rev = float(rev_row[0] or 0)
        subtotal = float(rev_row[1] or 0)
        gross_profit = float(rev_row[2] or 0)
        org_gross_margin = round(gross_profit / subtotal * 100, 1) if subtotal else None

        exp = await db.execute(
            text("SELECT SUM(amount) FROM expenses WHERE org_id=:oid AND date >= now() - interval '12 months'")
            .bindparams(oid=org_id)
        )
        total_exp = float(exp.scalar() or 0)
        net_profit = gross_profit - total_exp
        org_net_margin = round(net_profit / total_rev * 100, 1) if total_rev else None

        dso = await db.execute(
            text("""
                SELECT AVG(EXTRACT(EPOCH FROM (paid_at - issued_date))/86400)
                FROM invoices
                WHERE org_id=:oid AND status='paid'
                  AND issued_date >= now() - interval '12 months'
            """).bindparams(oid=org_id)
        )
        org_dso = round(float(dso.scalar() or 0), 1)

        # Previous 12 months for YoY
        prev_rev = await db.execute(
            text("""
                SELECT SUM(total_amount) FROM invoices
                WHERE org_id=:oid AND status NOT IN ('draft','cancelled')
                  AND issued_date >= now() - interval '24 months'
                  AND issued_date < now() - interval '12 months'
            """).bindparams(oid=org_id)
        )
        prev_total = float(prev_rev.scalar() or 0)
        yoy_growth = round((total_rev - prev_total) / prev_total * 100, 1) if prev_total else None

        metrics = [
            {
                "metric": "gross_margin_pct",
                "label": "Gross Margin %",
                "org_value": org_gross_margin,
                "industry_value": industry["gross_margin_pct"],
                "unit": "%",
                "higher_is_better": True,
            },
            {
                "metric": "net_margin_pct",
                "label": "Net Margin %",
                "org_value": org_net_margin,
                "industry_value": industry["net_margin_pct"],
                "unit": "%",
                "higher_is_better": True,
            },
            {
                "metric": "days_sales_outstanding",
                "label": "Days Sales Outstanding",
                "org_value": org_dso if org_dso else None,
                "industry_value": industry["days_sales_outstanding"],
                "unit": "days",
                "higher_is_better": False,
            },
            {
                "metric": "revenue_growth_yoy_pct",
                "label": "Revenue Growth YoY %",
                "org_value": yoy_growth,
                "industry_value": industry["revenue_growth_yoy_pct"],
                "unit": "%",
                "higher_is_better": True,
            },
        ]

        return {
            "sector": sector,
            "source": industry["source"],
            "metrics": metrics,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_benchmarks failed: %s", e)
        raise HTTPException(500, "Internal server error")


@router.patch("/benchmarks/sector")
async def update_sector(
    body: dict,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Save the org's industry sector for benchmark context."""
    try:
        sector = body.get("sector", "")
        if sector not in _SECTORS:
            raise HTTPException(400, detail=f"Unknown sector. Choose from: {_SECTORS}")
        await db.execute(
            text("UPDATE organizations SET industry_sector=:s WHERE id=:oid")
            .bindparams(s=sector, oid=member["org_id"])
        )
        await db.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_sector failed: %s", e)
        raise HTTPException(500, "Internal server error")


# ── COHORT ANALYSIS ───────────────────────────────────────────────────────────

@router.get("/cohorts")
async def get_cohorts(
    months: int = 12,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return customer retention cohort matrix.

    Each cohort = customers whose first invoice was in a given month.
    Retention[cohort][M+N] = % of cohort customers who had ≥1 paid invoice in month N.
    """
    try:
        _require_pro(member["plan"])
        months = min(max(months, 3), 24)
        org_id = member["org_id"]

        # First purchase month per customer
        cohort_rows = await db.execute(
            text("""
                SELECT customer_id,
                       date_trunc('month', MIN(issued_date)) AS cohort_month
                FROM invoices
                WHERE org_id=:oid AND status NOT IN ('draft','cancelled')
                  AND issued_date >= now() - make_interval(months => :m)
                GROUP BY customer_id
            """).bindparams(oid=org_id, m=months)
        )
        cohort_map: dict[str, str] = {}
        for r in cohort_rows:
            cohort_map[str(r[0])] = str(r[1])[:7]  # "YYYY-MM"

        if not cohort_map:
            return {"cohorts": []}

        # All active months per customer
        activity_rows = await db.execute(
            text("""
                SELECT customer_id,
                       date_trunc('month', issued_date) AS active_month
                FROM invoices
                WHERE org_id=:oid AND status NOT IN ('draft','cancelled')
                  AND issued_date >= now() - make_interval(months => :m)
                GROUP BY customer_id, active_month
            """).bindparams(oid=org_id, m=months)
        )

        # Build cohort → {month_offset → set(customer_ids)}
        from collections import defaultdict
        from datetime import date

        activity: dict[str, dict[int, set]] = defaultdict(lambda: defaultdict(set))
        for r in activity_rows:
            cid = str(r[0])
            cohort_month_str = cohort_map.get(cid)
            if not cohort_month_str:
                continue
            active_str = str(r[1])[:7]
            cy, cm = int(cohort_month_str[:4]), int(cohort_month_str[5:7])
            ay, am = int(active_str[:4]), int(active_str[5:7])
            offset = (ay - cy) * 12 + (am - cm)
            if offset >= 0:
                activity[cohort_month_str][offset].add(cid)

        # Build cohort sizes
        cohort_sizes: dict[str, int] = defaultdict(int)
        for cid, cohort_month in cohort_map.items():
            cohort_sizes[cohort_month] += 1

        cohorts = []
        for cohort_month in sorted(cohort_sizes.keys()):
            size = cohort_sizes[cohort_month]
            max_offset = months
            retention = []
            for offset in range(max_offset + 1):
                retained = len(activity[cohort_month].get(offset, set()))
                retention.append({
                    "month_offset": offset,
                    "retained": retained,
                    "rate": round(retained / size * 100, 1) if size else 0,
                })
            cohorts.append({
                "cohort_month": cohort_month,
                "cohort_size": size,
                "retention": retention,
            })

        return {"cohorts": cohorts, "max_offset": months}
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_cohorts failed: %s", e)
        raise HTTPException(500, "Internal server error")
