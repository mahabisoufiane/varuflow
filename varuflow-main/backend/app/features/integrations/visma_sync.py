"""Visma eEkonomi + Bokio accounting sync

Visma eEkonomi: API key + company GUID (Basic auth over HTTPS)
Bokio: API key stub (Bokio Open API is invite-only)

Endpoints:
  POST /api/integrations/visma/connect
  DELETE /api/integrations/visma/disconnect
  GET  /api/integrations/visma/status
  POST /api/integrations/visma/sync-invoices
  POST /api/integrations/visma/sync-customers

  POST /api/integrations/bokio/connect
  DELETE /api/integrations/bokio/disconnect
  GET  /api/integrations/bokio/status
  POST /api/integrations/bokio/sync-invoices   (stub)
  POST /api/integrations/bokio/sync-customers  (stub)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_plan
from .models import IntegrationConfig
from app.features.invoicing.models import Customer, Invoice, InvoiceStatus
from app.features.auth.organization import OrgPlan

router = APIRouter(tags=["integrations_accounting"])
log = logging.getLogger(__name__)

VISMA_API = "https://eaccountingapi.vismaonline.com/v2"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


async def _get_config(db: AsyncSession, org_id: uuid.UUID, provider: str) -> Optional[IntegrationConfig]:
    row = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.org_id == org_id,
            IntegrationConfig.provider == provider,
        )
    )
    return row.scalar_one_or_none()


# ── Schemas ───────────────────────────────────────────────────────────────────

class VismaConnectIn(BaseModel):
    api_key: str
    company_id: str   # Visma company GUID

class BokioConnectIn(BaseModel):
    api_key: str
    workspace_id: str

class SyncResult(BaseModel):
    synced: int
    skipped: int
    errors: int
    message: str

class StatusOut(BaseModel):
    provider: str
    connected: bool
    is_active: bool
    last_sync_at: Optional[str]
    last_sync_status: Optional[str]


# ── Visma endpoints ───────────────────────────────────────────────────────────

@router.post("/api/integrations/visma/connect")
async def visma_connect(
    body: VismaConnectIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    org_id = _org(ctx)
    try:
        # Validate credentials — list companies endpoint
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{VISMA_API}/me",
                auth=(body.api_key, body.company_id),
            )
        if resp.status_code == 401:
            raise HTTPException(status_code=422, detail="Invalid Visma credentials")

        cfg = await _get_config(db, org_id, "visma")
        creds = {"api_key": body.api_key, "company_id": body.company_id}
        if cfg:
            cfg.config = creds
            cfg.is_active = True
        else:
            cfg = IntegrationConfig(org_id=org_id, provider="visma", config=creds)
            db.add(cfg)
        await db.commit()
        return {"connected": True}
    except HTTPException:
        raise
    except Exception as e:
        log.error("visma_connect failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/integrations/visma/disconnect")
async def visma_disconnect(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "visma")
        if cfg:
            cfg.is_active = False
            cfg.config = {}
            await db.commit()
        return {"disconnected": True}
    except Exception as e:
        log.error("visma_disconnect failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/integrations/visma/status", response_model=StatusOut)
async def visma_status(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "visma")
        if not cfg:
            return StatusOut(provider="visma", connected=False, is_active=False,
                             last_sync_at=None, last_sync_status=None)
        return StatusOut(
            provider="visma", connected=cfg.is_active, is_active=cfg.is_active,
            last_sync_at=cfg.last_sync_at.isoformat() if cfg.last_sync_at else None,
            last_sync_status=cfg.last_sync_status,
        )
    except Exception as e:
        log.error("visma_status failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/integrations/visma/sync-invoices", response_model=SyncResult)
async def visma_sync_invoices(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "visma")
        if not cfg or not cfg.is_active:
            raise HTTPException(status_code=422, detail="Visma not connected")

        api_key = cfg.config.get("api_key")
        company_id = cfg.config.get("company_id")
        auth = (api_key, company_id)

        # Fetch SENT/PAID/OVERDUE invoices since last sync
        since = cfg.last_sync_at
        q = select(Invoice).where(
            Invoice.org_id == org_id,
            Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.PAID, InvoiceStatus.OVERDUE]),
        )
        if since:
            q = q.where(Invoice.updated_at >= since)
        rows = await db.execute(q.limit(100))
        invoices = rows.scalars().all()

        synced = errors = 0

        async with httpx.AsyncClient(timeout=30) as client:
            for inv in invoices:
                try:
                    issue_str = inv.issue_date.strftime("%Y-%m-%d") if hasattr(inv.issue_date, "strftime") else str(inv.issue_date)
                    payload = {
                        "InvoiceDate": issue_str,
                        "InvoiceNumber": inv.invoice_number,
                        "TotalAmount": float(inv.total_sek or 0),
                        "VATAmount": float(inv.vat_amount or 0),
                        "CurrencyCode": inv.currency or "SEK",
                        "Rows": [],
                    }
                    r = await client.post(
                        f"{VISMA_API}/customerinvoices",
                        json=payload,
                        auth=auth,
                    )
                    if r.status_code in (200, 201):
                        synced += 1
                    else:
                        errors += 1
                except Exception:
                    errors += 1

        cfg.last_sync_at = datetime.now(timezone.utc)
        cfg.last_sync_status = "success" if errors == 0 else "partial"
        await db.commit()

        return SyncResult(synced=synced, skipped=0, errors=errors,
                          message=f"Pushed {synced} invoices to Visma eEkonomi")
    except HTTPException:
        raise
    except Exception as e:
        log.error("visma_sync_invoices failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/integrations/visma/sync-customers", response_model=SyncResult)
async def visma_sync_customers(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "visma")
        if not cfg or not cfg.is_active:
            raise HTTPException(status_code=422, detail="Visma not connected")

        api_key = cfg.config.get("api_key")
        company_id = cfg.config.get("company_id")
        auth = (api_key, company_id)

        customers = await db.execute(
            select(Customer).where(Customer.org_id == org_id, Customer.deleted_at.is_(None)).limit(100)
        )
        synced = errors = 0

        async with httpx.AsyncClient(timeout=30) as client:
            for c in customers.scalars():
                try:
                    r = await client.post(
                        f"{VISMA_API}/customers",
                        json={"Name": c.company_name or "", "IsPrivatePerson": False},
                        auth=auth,
                    )
                    if r.status_code in (200, 201):
                        synced += 1
                    else:
                        errors += 1
                except Exception:
                    errors += 1

        cfg.last_sync_at = datetime.now(timezone.utc)
        cfg.last_sync_status = "success" if errors == 0 else "partial"
        await db.commit()

        return SyncResult(synced=synced, skipped=0, errors=errors,
                          message=f"Pushed {synced} customers to Visma")
    except HTTPException:
        raise
    except Exception as e:
        log.error("visma_sync_customers failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Bokio endpoints (stub — Bokio Open API is invite-only) ────────────────────

@router.post("/api/integrations/bokio/connect")
async def bokio_connect(
    body: BokioConnectIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "bokio")
        creds = {"api_key": body.api_key, "workspace_id": body.workspace_id}
        if cfg:
            cfg.config = creds
            cfg.is_active = True
        else:
            cfg = IntegrationConfig(org_id=org_id, provider="bokio", config=creds)
            db.add(cfg)
        await db.commit()
        return {"connected": True, "note": "Bokio credentials saved. Bokio Open API requires an invite from Bokio AB to activate sync."}
    except Exception as e:
        log.error("bokio_connect failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/integrations/bokio/disconnect")
async def bokio_disconnect(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "bokio")
        if cfg:
            cfg.is_active = False
            cfg.config = {}
            await db.commit()
        return {"disconnected": True}
    except Exception as e:
        log.error("bokio_disconnect failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/integrations/bokio/status", response_model=StatusOut)
async def bokio_status(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "bokio")
        if not cfg:
            return StatusOut(provider="bokio", connected=False, is_active=False,
                             last_sync_at=None, last_sync_status=None)
        return StatusOut(
            provider="bokio", connected=cfg.is_active, is_active=cfg.is_active,
            last_sync_at=cfg.last_sync_at.isoformat() if cfg.last_sync_at else None,
            last_sync_status=cfg.last_sync_status,
        )
    except Exception as e:
        log.error("bokio_status failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/integrations/bokio/sync-invoices", response_model=SyncResult)
async def bokio_sync_invoices(
    ctx: tuple = Depends(get_current_member),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    return SyncResult(
        synced=0, skipped=0, errors=0,
        message="Bokio Open API requires an invite from Bokio AB. Visit https://www.bokio.se/partner to apply for API access.",
    )


@router.post("/api/integrations/bokio/sync-customers", response_model=SyncResult)
async def bokio_sync_customers(
    ctx: tuple = Depends(get_current_member),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    return SyncResult(
        synced=0, skipped=0, errors=0,
        message="Bokio Open API requires an invite from Bokio AB. Visit https://www.bokio.se/partner to apply for API access.",
    )
