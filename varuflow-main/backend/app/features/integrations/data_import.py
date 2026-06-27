"""Data Migration / Import Wizard.

Endpoints
─────────
GET  /api/data-import/jobs                → list import jobs
POST /api/data-import/upload              → upload CSV, returns parsed preview + job id
POST /api/data-import/jobs/{id}/mapping   → save column mapping
POST /api/data-import/jobs/{id}/execute   → run import (async-safe: marks status then processes)
GET  /api/data-import/jobs/{id}           → job status + validation errors
DELETE /api/data-import/jobs/{id}         → cancel/delete a pending job
"""
from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.features.inventory.import_job import ImportJob
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/data-import", tags=["data_import"], dependencies=[Depends(require_module("inventory"))])
log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

IMPORT_TYPES = {"customers", "products", "invoices", "suppliers", "chart_of_accounts", "inventory"}
SOURCE_SYSTEMS = {"quickbooks", "xero", "fortnox", "sage", "visma", "csv", "excel"}
MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB

# Canonical destination fields per import type
FIELD_OPTIONS: dict[str, list[str]] = {
    "customers": [
        "company_name", "org_number", "email", "phone",
        "address", "city", "postal_code", "country", "vat_number",
        "payment_terms", "credit_limit", "notes", "skip",
    ],
    "products": [
        "name", "sku", "barcode", "description", "price",
        "cost_price", "tax_rate", "unit", "category",
        "reorder_point", "lead_time_days", "is_active", "skip",
    ],
    "suppliers": [
        "name", "org_number", "email", "phone", "address",
        "city", "postal_code", "country", "vat_number",
        "payment_terms", "lead_time_days", "notes", "skip",
    ],
    "invoices": [
        "invoice_number", "customer_name", "issue_date", "due_date",
        "subtotal", "vat_amount", "total", "currency", "status",
        "notes", "skip",
    ],
    "chart_of_accounts": [
        "account_number", "account_name", "account_type",
        "vat_code", "description", "skip",
    ],
    "inventory": [
        "sku", "warehouse", "quantity", "cost_per_unit", "skip",
    ],
}


# ── Schemas ────────────────────────────────────────────────────────────────────

class JobOut(BaseModel):
    id: str
    import_type: str
    status: str
    filename: Optional[str]
    source_system: Optional[str]
    total_rows: Optional[int]
    imported_rows: Optional[int]
    failed_rows: Optional[int]
    validation_errors: Optional[Any]
    error_message: Optional[str]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]


class JobsOut(BaseModel):
    jobs: list[JobOut]
    total: int


class UploadPreview(BaseModel):
    job_id: str
    headers: list[str]          # original CSV column names
    preview_rows: list[list[str]]   # first 5 rows, raw strings
    suggested_mapping: dict[str, str]  # col_name → dest_field (best guess)
    available_fields: list[str]
    total_rows: int


class MappingIn(BaseModel):
    column_mapping: dict[str, str]   # csv_column → dest_field (or "skip")


class ValidationResult(BaseModel):
    valid_rows: int
    invalid_rows: int
    errors: list[dict[str, Any]]  # [{row, column, message}]


def _out(j: ImportJob) -> JobOut:
    return JobOut(
        id=str(j.id),
        import_type=j.import_type,
        status=j.status,
        filename=j.filename,
        source_system=j.source_system,
        total_rows=j.total_rows,
        imported_rows=j.imported_rows,
        failed_rows=j.failed_rows,
        validation_errors=j.validation_errors,
        error_message=j.error_message,
        created_at=j.created_at.isoformat(),
        started_at=j.started_at.isoformat() if j.started_at else None,
        completed_at=j.completed_at.isoformat() if j.completed_at else None,
    )


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _member_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.id


# ── Field name normaliser (best-effort header → dest_field mapping) ────────────

def _suggest_mapping(headers: list[str], import_type: str) -> dict[str, str]:
    """Heuristic: lowercase + strip → find the closest dest field name."""
    available = FIELD_OPTIONS.get(import_type, [])
    mapping: dict[str, str] = {}
    for h in headers:
        clean = h.lower().strip().replace(" ", "_").replace("-", "_")
        # Exact match wins
        if clean in available:
            mapping[h] = clean
            continue
        # Common aliases
        aliases = {
            "company": "company_name", "organisation": "company_name",
            "organization": "company_name", "org": "company_name",
            "e_mail": "email", "mail": "email",
            "telephone": "phone", "tel": "phone", "mobile": "phone",
            "item_name": "name", "product_name": "name",
            "item_number": "sku", "article_number": "sku",
            "sale_price": "price", "selling_price": "price",
            "purchase_price": "cost_price",
            "moms": "tax_rate", "vat": "tax_rate",
            "qty": "quantity", "stock": "quantity",
        }
        if clean in aliases and aliases[clean] in available:
            mapping[h] = aliases[clean]
        else:
            mapping[h] = "skip"
    return mapping


def _parse_csv(content: bytes, max_preview: int = 5) -> tuple[list[str], list[list[str]], int]:
    """Return (headers, preview_rows, total_data_rows)."""
    text = content.decode("utf-8-sig", errors="replace")  # strip BOM
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return [], [], 0
    headers = [h.strip() for h in rows[0]]
    data_rows = rows[1:]
    preview = [row for row in data_rows[:max_preview]]
    return headers, preview, len(data_rows)


def _validate_rows(
    headers: list[str],
    all_rows: list[list[str]],
    mapping: dict[str, str],
    import_type: str,
) -> tuple[int, int, list[dict[str, Any]]]:
    """Basic validation — required field presence, numeric checks."""
    required: dict[str, list[str]] = {
        "customers": ["company_name"],
        "products": ["name"],
        "suppliers": ["name"],
        "invoices": ["invoice_number", "issue_date", "total"],
        "chart_of_accounts": ["account_number", "account_name"],
        "inventory": ["sku", "quantity"],
    }
    required_dest = set(required.get(import_type, []))
    dest_to_col = {v: k for k, v in mapping.items() if v != "skip"}

    errors: list[dict[str, Any]] = []
    valid = 0
    invalid = 0
    for r_idx, row in enumerate(all_rows, start=2):  # 2 = 1-indexed + header
        row_dict = {headers[i]: (row[i] if i < len(row) else "") for i in range(len(headers))}
        row_errors = []
        for req_field in required_dest:
            col = dest_to_col.get(req_field)
            if col is None:
                row_errors.append({"row": r_idx, "column": req_field, "message": "Required field not mapped"})
            elif not row_dict.get(col, "").strip():
                row_errors.append({"row": r_idx, "column": col, "message": f"{req_field} is required"})
        # Numeric fields
        for num_field in ("price", "cost_price", "quantity", "total", "subtotal", "vat_amount", "credit_limit"):
            col = dest_to_col.get(num_field)
            if col and row_dict.get(col, "").strip():
                try:
                    float(row_dict[col].replace(",", "."))
                except ValueError:
                    row_errors.append({"row": r_idx, "column": col, "message": f"'{row_dict[col]}' is not a valid number"})
        if row_errors:
            errors.extend(row_errors)
            invalid += 1
        else:
            valid += 1
    return valid, invalid, errors[:200]  # cap error list


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/jobs", response_model=JobsOut)
async def list_jobs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        from sqlalchemy import func as sqlfunc, select as sa_select
        total = (await db.scalar(
            sa_select(sqlfunc.count(ImportJob.id)).where(ImportJob.org_id == org_id)
        )) or 0
        rows = await db.execute(
            select(ImportJob)
            .where(ImportJob.org_id == org_id)
            .order_by(ImportJob.created_at.desc())
            .limit(limit).offset((page - 1) * limit)
        )
        return JobsOut(jobs=[_out(j) for j in rows.scalars()], total=total)
    except Exception as e:
        log.error("list_import_jobs failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/upload", response_model=UploadPreview)
async def upload_file(
    file: UploadFile = File(...),
    import_type: str = Query(...),
    source_system: str = Query(default="csv"),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """
    Accept a CSV (or Excel exported as CSV) and return a parsed preview with
    auto-suggested column mapping.  XLSX support: ask the user to export as
    CSV in Excel first (avoids openpyxl dependency on Railway).
    """
    org_id = _org(ctx)
    try:
        if import_type not in IMPORT_TYPES:
            raise HTTPException(status_code=422, detail=f"import_type must be one of {sorted(IMPORT_TYPES)}")
        if source_system not in SOURCE_SYSTEMS:
            raise HTTPException(status_code=422, detail=f"source_system must be one of {sorted(SOURCE_SYSTEMS)}")

        content = await file.read()
        if len(content) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail="File exceeds 20 MB limit")
        if not content:
            raise HTTPException(status_code=422, detail="File is empty")

        headers, preview, total_rows = _parse_csv(content)
        if not headers:
            raise HTTPException(status_code=422, detail="Could not parse CSV — check encoding (UTF-8) and delimiter (comma)")

        suggested = _suggest_mapping(headers, import_type)

        # Store raw CSV in memory representation; for production a cloud
        # storage upload would go here. For now we store the column mapping
        # and row count; the execute endpoint re-parses from a re-upload.
        job = ImportJob(
            org_id=org_id,
            created_by=_member_id(ctx),
            import_type=import_type,
            status="ready",
            filename=file.filename or "upload.csv",
            source_system=source_system,
            total_rows=total_rows,
            column_mapping=suggested,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        return UploadPreview(
            job_id=str(job.id),
            headers=headers,
            preview_rows=preview,
            suggested_mapping=suggested,
            available_fields=FIELD_OPTIONS.get(import_type, []),
            total_rows=total_rows,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error("upload_import_file failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/jobs/{job_id}/mapping", response_model=JobOut)
async def save_mapping(
    job_id: uuid.UUID,
    body: MappingIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        job = await db.scalar(
            select(ImportJob).where(ImportJob.id == job_id, ImportJob.org_id == org_id)
        )
        if not job:
            raise HTTPException(status_code=404, detail="Import job not found")
        if job.status not in ("ready", "failed"):
            raise HTTPException(status_code=409, detail=f"Cannot update mapping in status '{job.status}'")
        job.column_mapping = body.column_mapping
        await db.commit()
        await db.refresh(job)
        return _out(job)
    except HTTPException:
        raise
    except Exception as e:
        log.error("save_import_mapping failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/jobs/{job_id}/validate", response_model=ValidationResult)
async def validate_job(
    job_id: uuid.UUID,
    file: UploadFile = File(...),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Re-upload the same file to run validation with the saved mapping."""
    org_id = _org(ctx)
    try:
        job = await db.scalar(
            select(ImportJob).where(ImportJob.id == job_id, ImportJob.org_id == org_id)
        )
        if not job:
            raise HTTPException(status_code=404, detail="Import job not found")

        content = await file.read()
        headers, _, _ = _parse_csv(content, max_preview=0)
        _, all_rows, total = _parse_csv(content)
        # Re-parse all rows
        text = content.decode("utf-8-sig", errors="replace")
        rows_all = list(csv.reader(io.StringIO(text)))[1:]

        mapping = job.column_mapping or {}
        valid_count, invalid_count, errors = _validate_rows(headers, rows_all, mapping, job.import_type)

        job.total_rows = total
        job.validation_errors = errors[:100] if errors else None
        await db.commit()

        return ValidationResult(valid_rows=valid_count, invalid_rows=invalid_count, errors=errors[:50])
    except HTTPException:
        raise
    except Exception as e:
        log.error("validate_import_job failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/jobs/{job_id}/execute", response_model=JobOut)
async def execute_job(
    job_id: uuid.UUID,
    file: UploadFile = File(...),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """
    Execute the import.  Each row is processed individually — invalid rows
    are skipped and counted under failed_rows; valid rows are inserted.
    Currently supports: customers, products, suppliers.
    invoices / chart_of_accounts / inventory are stubbed (marked todo).
    """
    org_id = _org(ctx)
    try:
        job = await db.scalar(
            select(ImportJob).where(ImportJob.id == job_id, ImportJob.org_id == org_id)
        )
        if not job:
            raise HTTPException(status_code=404, detail="Import job not found")
        if job.status == "importing":
            raise HTTPException(status_code=409, detail="Import already in progress")
        if not job.column_mapping:
            raise HTTPException(status_code=422, detail="Save column mapping before executing")

        job.status = "importing"
        job.started_at = datetime.now(timezone.utc)
        await db.commit()

        content = await file.read()
        text = content.decode("utf-8-sig", errors="replace")
        all_rows = list(csv.reader(io.StringIO(text)))
        headers = [h.strip() for h in (all_rows[0] if all_rows else [])]
        data_rows = all_rows[1:]

        mapping = job.column_mapping  # col_name → dest_field
        imported = 0
        failed = 0
        errors: list[dict] = []

        def get(row: list[str], col_name: str) -> str:
            try:
                idx = headers.index(col_name)
                return row[idx].strip() if idx < len(row) else ""
            except ValueError:
                return ""

        def dest(row: list[str], dest_field: str) -> str:
            for col, d in mapping.items():
                if d == dest_field:
                    return get(row, col)
            return ""

        if job.import_type == "customers":
            from app.features.invoicing.models import Customer
            for r_idx, row in enumerate(data_rows, start=2):
                try:
                    name = dest(row, "company_name")
                    if not name:
                        failed += 1
                        errors.append({"row": r_idx, "message": "company_name missing"})
                        continue
                    cust = Customer(
                        org_id=org_id,
                        company_name=name[:255],
                        org_number=dest(row, "org_number")[:20] or None,
                        email=dest(row, "email")[:255] or None,
                        phone=dest(row, "phone")[:50] or None,
                        address=dest(row, "address")[:500] or None,
                        vat_number=dest(row, "vat_number")[:30] or None,
                    )
                    db.add(cust)
                    imported += 1
                except Exception as row_e:
                    failed += 1
                    errors.append({"row": r_idx, "message": str(row_e)})
            await db.flush()

        elif job.import_type == "products":
            from app.features.inventory.models import Product
            for r_idx, row in enumerate(data_rows, start=2):
                try:
                    name = dest(row, "name")
                    if not name:
                        failed += 1
                        errors.append({"row": r_idx, "message": "name missing"})
                        continue
                    price_str = dest(row, "price").replace(",", ".")
                    sell_price = float(price_str) if price_str else 0.0
                    cost_str = dest(row, "cost_price").replace(",", ".")
                    purchase_price = float(cost_str) if cost_str else 0.0
                    tax_str = dest(row, "tax_rate").replace(",", ".").rstrip("%")
                    tax = float(tax_str) if tax_str else 25.0
                    sku_val = dest(row, "sku") or f"IMPORT-{r_idx}"
                    prod = Product(
                        org_id=org_id,
                        name=name[:255],
                        sku=sku_val[:100],
                        description=dest(row, "description")[:1000] or None,
                        sell_price=sell_price,
                        purchase_price=purchase_price,
                        tax_rate=tax,
                        unit=dest(row, "unit")[:50] or "st",
                    )
                    db.add(prod)
                    imported += 1
                except Exception as row_e:
                    failed += 1
                    errors.append({"row": r_idx, "message": str(row_e)})
            await db.flush()

        elif job.import_type == "suppliers":
            from app.features.inventory.models import Supplier
            for r_idx, row in enumerate(data_rows, start=2):
                try:
                    name = dest(row, "name")
                    if not name:
                        failed += 1
                        errors.append({"row": r_idx, "message": "name missing"})
                        continue
                    sup = Supplier(
                        org_id=org_id,
                        name=name[:255],
                        email=dest(row, "email")[:255] or None,
                        phone=dest(row, "phone")[:50] or None,
                        address=dest(row, "address")[:500] or None,
                        country=dest(row, "country")[:100] or "Sweden",
                    )
                    db.add(sup)
                    imported += 1
                except Exception as row_e:
                    failed += 1
                    errors.append({"row": r_idx, "message": str(row_e)})
            await db.flush()

        else:
            # Stub for invoices / chart_of_accounts / inventory
            failed = len(data_rows)
            errors = [{"row": 1, "message": f"Import type '{job.import_type}' requires manual setup — contact support"}]

        job.status = "done" if not errors else "done_with_errors"
        job.imported_rows = imported
        job.failed_rows = failed
        job.validation_errors = errors[:100] if errors else None
        job.completed_at = datetime.now(timezone.utc)
        job.total_rows = imported + failed
        await db.commit()
        await db.refresh(job)
        return _out(job)

    except HTTPException:
        raise
    except Exception as e:
        log.error("execute_import_job failed: %s", e, extra={"org_id": str(org_id)})
        # Mark job as failed
        try:
            j = await db.scalar(select(ImportJob).where(ImportJob.id == job_id))
            if j:
                j.status = "failed"
                j.error_message = str(e)[:500]
                await db.commit()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(
    job_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        job = await db.scalar(
            select(ImportJob).where(ImportJob.id == job_id, ImportJob.org_id == org_id)
        )
        if not job:
            raise HTTPException(status_code=404, detail="Import job not found")
        return _out(job)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_import_job failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        job = await db.scalar(
            select(ImportJob).where(ImportJob.id == job_id, ImportJob.org_id == org_id)
        )
        if not job:
            raise HTTPException(status_code=404, detail="Import job not found")
        if job.status == "importing":
            raise HTTPException(status_code=409, detail="Cannot delete a running import job")
        await db.delete(job)
        await db.commit()
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_import_job failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
