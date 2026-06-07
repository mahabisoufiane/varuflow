"""Report Builder router.

No-code report definitions: filter, group, aggregate over core entities.
"""
import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.report_builder import SavedReport, RbScheduledReport

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports-builder", tags=["report-builder"], dependencies=[Depends(require_module("analytics"))])

# ── Safe entity → table + allowed fields map ─────────────────────────────────
# Only these entities and fields can be queried. This prevents arbitrary SQL injection
# by whitelisting every table name and column through code, never through user input.

_ENTITY_MAP: dict[str, dict] = {
    "invoices": {
        "table": "invoices",
        "org_col": "org_id",
        "fields": {
            "id": "id", "status": "status", "total_amount": "total_amount",
            "created_at": "created_at", "due_date": "due_date", "customer_id": "customer_id",
        },
    },
    "customers": {
        "table": "customers",
        "org_col": "org_id",
        "fields": {
            "id": "id", "name": "name", "email": "email",
            "created_at": "created_at", "country": "country",
        },
    },
    "products": {
        "table": "products",
        "org_col": "org_id",
        "fields": {
            "id": "id", "name": "name", "sku": "sku", "category": "category",
            "sell_price": "sell_price", "purchase_price": "purchase_price",
            "created_at": "created_at",
        },
    },
    "purchase_orders": {
        "table": "purchase_orders",
        "org_col": "org_id",
        "fields": {
            "id": "id", "status": "status", "total_amount": "total_amount",
            "created_at": "created_at", "supplier_id": "supplier_id",
        },
    },
}

_VALID_OPS = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "like"}
_VALID_AGGS = {"count", "sum", "avg", "min", "max"}
_VALID_SORT = {"asc", "desc"}

# ── Run engine ────────────────────────────────────────────────────────────────

async def _run_report(report: SavedReport, org_id: uuid.UUID, db: AsyncSession) -> list[dict]:
    """Execute a saved report config against the database.

    All table/column names are resolved through the whitelist in _ENTITY_MAP.
    No user string is ever interpolated directly into SQL.
    """
    entity = _ENTITY_MAP.get(report.entity)
    if not entity:
        raise HTTPException(status_code=422, detail=f"Unknown entity: {report.entity}")

    table = entity["table"]
    org_col = entity["org_col"]
    allowed_fields = entity["fields"]

    # Build parameterised WHERE clauses
    where_parts = [f'"{table}"."{org_col}" = :org_id']
    params: dict[str, Any] = {"org_id": str(org_id)}

    for i, f in enumerate(report.filters or []):
        field = f.get("field")
        op = f.get("operator")
        value = f.get("value")
        if field not in allowed_fields or op not in _VALID_OPS:
            continue
        col = allowed_fields[field]
        key = f"filter_{i}"
        if op == "eq":
            where_parts.append(f'"{table}"."{col}" = :{key}')
        elif op == "ne":
            where_parts.append(f'"{table}"."{col}" != :{key}')
        elif op == "gt":
            where_parts.append(f'"{table}"."{col}" > :{key}')
        elif op == "gte":
            where_parts.append(f'"{table}"."{col}" >= :{key}')
        elif op == "lt":
            where_parts.append(f'"{table}"."{col}" < :{key}')
        elif op == "lte":
            where_parts.append(f'"{table}"."{col}" <= :{key}')
        elif op == "like":
            where_parts.append(f'"{table}"."{col}" ILIKE :{key}')
            value = f"%{value}%"
        elif op == "in" and isinstance(value, list):
            in_keys = [f"{key}_{j}" for j in range(len(value))]
            where_parts.append(f'"{table}"."{col}" IN ({", ".join(f":{k}" for k in in_keys)})')
            for k, v in zip(in_keys, value):
                params[k] = v
            params.pop(key, None)
            continue
        params[key] = value

    # SELECT: group_by columns + aggregates
    select_parts = []
    group_cols: list[str] = []
    for g in (report.group_by or []):
        if g in allowed_fields:
            col = allowed_fields[g]
            select_parts.append(f'"{table}"."{col}" AS "{g}"')
            group_cols.append(f'"{table}"."{col}"')

    for agg in (report.aggregates or []):
        col_name = agg.get("column")
        agg_func = agg.get("func", "count")
        if agg_func not in _VALID_AGGS:
            continue
        if agg_func == "count":
            select_parts.append(f'COUNT(*) AS "{agg_func}_{col_name}"')
        elif col_name in allowed_fields:
            actual_col = allowed_fields[col_name]
            select_parts.append(f'{agg_func.upper()}("{table}"."{actual_col}") AS "{agg_func}_{col_name}"')

    if not select_parts:
        select_parts = [f'"{table}".*']

    sql_parts = [
        f'SELECT {", ".join(select_parts)}',
        f'FROM "{table}"',
        f'WHERE {" AND ".join(where_parts)}',
    ]
    if group_cols:
        sql_parts.append(f'GROUP BY {", ".join(group_cols)}')

    # ORDER BY
    sort_by = report.sort_by
    sort_dir = report.sort_dir if report.sort_dir in _VALID_SORT else "asc"
    if sort_by and sort_by in allowed_fields:
        actual_sort = allowed_fields[sort_by]
        sql_parts.append(f'ORDER BY "{table}"."{actual_sort}" {sort_dir.upper()}')

    sql_parts.append("LIMIT 1000")

    sql = " ".join(sql_parts)
    result = await db.execute(text(sql), params)
    rows = result.mappings().all()
    return [dict(r) for r in rows]


# ── Schemas ───────────────────────────────────────────────────────────────────

class ReportCreateIn(BaseModel):
    name: str
    entity: str
    filters: list = []
    group_by: list = []
    aggregates: list = []
    columns: list = []
    sort_by: Optional[str] = None
    sort_dir: str = "asc"
    chart_type: Optional[str] = None
    is_shared: bool = False


class ReportUpdateIn(BaseModel):
    name: Optional[str] = None
    filters: Optional[list] = None
    group_by: Optional[list] = None
    aggregates: Optional[list] = None
    columns: Optional[list] = None
    sort_by: Optional[str] = None
    sort_dir: Optional[str] = None
    chart_type: Optional[str] = None
    is_shared: Optional[bool] = None


class ScheduleReportIn(BaseModel):
    recipient_emails: list[str]
    cron_expression: str
    export_format: str = "csv"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_reports(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        result = await db.execute(
            select(SavedReport)
            .where(SavedReport.org_id == org_id)
            .order_by(SavedReport.name)
        )
        reports = result.scalars().all()
        return {
            "items": [
                {"id": str(r.id), "name": r.name, "entity": r.entity,
                 "is_shared": r.is_shared, "chart_type": r.chart_type,
                 "created_at": r.created_at.isoformat()}
                for r in reports
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_reports failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_report(
    body: ReportCreateIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        user_id = uuid.UUID(str(member["user_id"]))
        if body.entity not in _ENTITY_MAP:
            raise HTTPException(status_code=422, detail=f"Unknown entity: {body.entity}")
        report = SavedReport(
            id=uuid.uuid4(), org_id=org_id, created_by=user_id,
            name=body.name, entity=body.entity, filters=body.filters,
            group_by=body.group_by, aggregates=body.aggregates, columns=body.columns,
            sort_by=body.sort_by, sort_dir=body.sort_dir, chart_type=body.chart_type,
            is_shared=body.is_shared,
        )
        db.add(report)
        await db.commit()
        await db.refresh(report)
        return {"id": str(report.id), "name": report.name}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"create_report failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/entities")
async def list_entities(member=Depends(get_current_member)):
    """Return available entities and their queryable fields."""
    return {
        "entities": [
            {"entity": k, "fields": list(v["fields"].keys())}
            for k, v in _ENTITY_MAP.items()
        ]
    }


@router.get("/{report_id}")
async def get_report(
    report_id: uuid.UUID,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        report = await db.get(SavedReport, report_id)
        if not report or report.org_id != org_id:
            raise HTTPException(status_code=404, detail="Report not found")
        return {
            "id": str(report.id), "name": report.name, "entity": report.entity,
            "filters": report.filters, "group_by": report.group_by,
            "aggregates": report.aggregates, "columns": report.columns,
            "sort_by": report.sort_by, "sort_dir": report.sort_dir,
            "chart_type": report.chart_type, "is_shared": report.is_shared,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_report failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{report_id}")
async def update_report(
    report_id: uuid.UUID,
    body: ReportUpdateIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        report = await db.get(SavedReport, report_id)
        if not report or report.org_id != org_id:
            raise HTTPException(status_code=404, detail="Report not found")
        for field, val in body.model_dump(exclude_unset=True).items():
            setattr(report, field, val)
        await db.commit()
        return {"id": str(report.id), "name": report.name}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"update_report failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{report_id}", status_code=204)
async def delete_report(
    report_id: uuid.UUID,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        report = await db.get(SavedReport, report_id)
        if not report or report.org_id != org_id:
            raise HTTPException(status_code=404, detail="Report not found")
        await db.delete(report)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"delete_report failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{report_id}/run")
async def run_report(
    report_id: uuid.UUID,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        report = await db.get(SavedReport, report_id)
        if not report or report.org_id != org_id:
            raise HTTPException(status_code=404, detail="Report not found")
        rows = await _run_report(report, org_id, db)
        return {"report_id": str(report_id), "name": report.name, "entity": report.entity,
                "rows": rows, "count": len(rows)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"run_report failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{report_id}/schedule", status_code=201)
async def schedule_report(
    report_id: uuid.UUID,
    body: ScheduleReportIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        report = await db.get(SavedReport, report_id)
        if not report or report.org_id != org_id:
            raise HTTPException(status_code=404, detail="Report not found")
        sched = RbScheduledReport(
            id=uuid.uuid4(), org_id=org_id, report_id=report_id,
            recipient_emails=body.recipient_emails, cron_expression=body.cron_expression,
            export_format=body.export_format,
        )
        db.add(sched)
        await db.commit()
        return {"id": str(sched.id)}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"schedule_report failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")
