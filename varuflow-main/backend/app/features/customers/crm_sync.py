"""HubSpot + Salesforce CRM sync

HubSpot: Private App token (Bearer auth)
Salesforce: OAuth tokens (instance_url + access_token supplied by user)

Endpoints:
  POST /api/integrations/hubspot/connect
  DELETE /api/integrations/hubspot/disconnect
  GET  /api/integrations/hubspot/status
  POST /api/integrations/hubspot/sync-customers
  POST /api/integrations/hubspot/sync-deals
  POST /api/integrations/hubspot/pull-contacts

  POST /api/integrations/salesforce/connect
  DELETE /api/integrations/salesforce/disconnect
  GET  /api/integrations/salesforce/status
  POST /api/integrations/salesforce/sync-customers
  POST /api/integrations/salesforce/sync-deals
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
from .models import Deal
from app.features.integrations.models import IntegrationConfig
from app.features.invoicing.models import Customer
from app.features.auth.organization import OrgPlan

router = APIRouter(tags=["integrations_crm"])
log = logging.getLogger(__name__)

HUBSPOT_API = "https://api.hubapi.com"
SALESFORCE_API_VERSION = "v57.0"


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

class HubSpotConnectIn(BaseModel):
    access_token: str   # HubSpot Private App token

class SalesforceConnectIn(BaseModel):
    instance_url: str   # e.g. https://myorg.salesforce.com
    access_token: str
    refresh_token: Optional[str] = None

class SyncResult(BaseModel):
    pushed: int
    skipped: int
    errors: int
    message: str

class StatusOut(BaseModel):
    provider: str
    connected: bool
    is_active: bool
    last_sync_at: Optional[str]
    last_sync_status: Optional[str]


# ── HubSpot endpoints ─────────────────────────────────────────────────────────

@router.post("/api/integrations/hubspot/connect")
async def hubspot_connect(
    body: HubSpotConnectIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    org_id = _org(ctx)
    try:
        # Validate token
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{HUBSPOT_API}/crm/v3/objects/contacts",
                params={"limit": 1},
                headers={"Authorization": f"Bearer {body.access_token}"},
            )
        if resp.status_code == 401:
            raise HTTPException(status_code=422, detail="Invalid HubSpot access token")

        cfg = await _get_config(db, org_id, "hubspot")
        if cfg:
            cfg.config = {"access_token": body.access_token}
            cfg.is_active = True
        else:
            cfg = IntegrationConfig(org_id=org_id, provider="hubspot",
                                    config={"access_token": body.access_token})
            db.add(cfg)
        await db.commit()
        return {"connected": True}
    except HTTPException:
        raise
    except Exception as e:
        log.error("hubspot_connect failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/integrations/hubspot/disconnect")
async def hubspot_disconnect(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "hubspot")
        if cfg:
            cfg.is_active = False
            cfg.config = {}
            await db.commit()
        return {"disconnected": True}
    except Exception as e:
        log.error("hubspot_disconnect failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/integrations/hubspot/status", response_model=StatusOut)
async def hubspot_status(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "hubspot")
        if not cfg:
            return StatusOut(provider="hubspot", connected=False, is_active=False,
                             last_sync_at=None, last_sync_status=None)
        return StatusOut(
            provider="hubspot", connected=cfg.is_active, is_active=cfg.is_active,
            last_sync_at=cfg.last_sync_at.isoformat() if cfg.last_sync_at else None,
            last_sync_status=cfg.last_sync_status,
        )
    except Exception as e:
        log.error("hubspot_status failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/integrations/hubspot/sync-customers", response_model=SyncResult)
async def hubspot_sync_customers(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "hubspot")
        if not cfg or not cfg.is_active:
            raise HTTPException(status_code=422, detail="HubSpot not connected")
        token = cfg.config.get("access_token")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        customers = await db.execute(
            select(Customer).where(Customer.org_id == org_id, Customer.deleted_at.is_(None))
        )
        pushed = skipped = errors = 0

        async with httpx.AsyncClient(timeout=30) as client:
            for customer in customers.scalars():
                try:
                    props = {
                        "company": customer.company_name or "",
                        "firstname": "",
                        "lastname": customer.company_name or "",
                    }
                    r = await client.post(
                        f"{HUBSPOT_API}/crm/v3/objects/contacts",
                        json={"properties": props},
                        headers=headers,
                    )
                    if r.status_code in (200, 201):
                        pushed += 1
                    elif r.status_code == 409:  # conflict — already exists
                        skipped += 1
                    else:
                        errors += 1
                except Exception:
                    errors += 1

        cfg.last_sync_at = datetime.now(timezone.utc)
        cfg.last_sync_status = "success" if errors == 0 else "partial"
        await db.commit()

        return SyncResult(pushed=pushed, skipped=skipped, errors=errors,
                          message=f"Pushed {pushed} customers to HubSpot")
    except HTTPException:
        raise
    except Exception as e:
        log.error("hubspot_sync_customers failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/integrations/hubspot/sync-deals", response_model=SyncResult)
async def hubspot_sync_deals(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "hubspot")
        if not cfg or not cfg.is_active:
            raise HTTPException(status_code=422, detail="HubSpot not connected")
        token = cfg.config.get("access_token")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        deals = await db.execute(
            select(Deal).where(Deal.org_id == org_id)
        )
        pushed = skipped = errors = 0

        async with httpx.AsyncClient(timeout=30) as client:
            for deal in deals.scalars():
                try:
                    props = {
                        "dealname": deal.title,
                        "amount": str(deal.value or 0),
                        "dealstage": deal.stage or "appointmentscheduled",
                        "pipeline": "default",
                    }
                    r = await client.post(
                        f"{HUBSPOT_API}/crm/v3/objects/deals",
                        json={"properties": props},
                        headers=headers,
                    )
                    if r.status_code in (200, 201):
                        pushed += 1
                    else:
                        errors += 1
                except Exception:
                    errors += 1

        cfg.last_sync_at = datetime.now(timezone.utc)
        cfg.last_sync_status = "success" if errors == 0 else "partial"
        await db.commit()

        return SyncResult(pushed=pushed, skipped=skipped, errors=errors,
                          message=f"Pushed {pushed} deals to HubSpot")
    except HTTPException:
        raise
    except Exception as e:
        log.error("hubspot_sync_deals failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/integrations/hubspot/pull-contacts", response_model=SyncResult)
async def hubspot_pull_contacts(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "hubspot")
        if not cfg or not cfg.is_active:
            raise HTTPException(status_code=422, detail="HubSpot not connected")
        token = cfg.config.get("access_token")
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{HUBSPOT_API}/crm/v3/objects/contacts",
                params={"limit": 50, "properties": "company,firstname,lastname"},
                headers=headers,
            )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"HubSpot API error: {resp.status_code}")

        contacts = resp.json().get("results", [])
        imported = skipped = errors = 0

        for contact in contacts:
            try:
                props = contact.get("properties", {})
                company_name = (
                    props.get("company")
                    or f"{props.get('firstname', '')} {props.get('lastname', '')}".strip()
                    or "HubSpot Contact"
                )
                existing = await db.execute(
                    select(Customer).where(
                        Customer.org_id == org_id,
                        Customer.company_name == company_name,
                    )
                )
                if existing.scalar_one_or_none():
                    skipped += 1
                    continue
                db.add(Customer(org_id=org_id, company_name=company_name))
                imported += 1
            except Exception:
                errors += 1

        await db.commit()
        return SyncResult(pushed=imported, skipped=skipped, errors=errors,
                          message=f"Imported {imported} HubSpot contacts")
    except HTTPException:
        raise
    except Exception as e:
        log.error("hubspot_pull_contacts failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Salesforce endpoints ───────────────────────────────────────────────────────

@router.post("/api/integrations/salesforce/connect")
async def salesforce_connect(
    body: SalesforceConnectIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    org_id = _org(ctx)
    try:
        instance = body.instance_url.rstrip("/")
        # Validate token via /services/data endpoint
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{instance}/services/data/",
                headers={"Authorization": f"Bearer {body.access_token}"},
            )
        if resp.status_code == 401:
            raise HTTPException(status_code=422, detail="Invalid Salesforce access token")

        cfg = await _get_config(db, org_id, "salesforce")
        creds = {
            "instance_url": instance,
            "access_token": body.access_token,
            "refresh_token": body.refresh_token,
        }
        if cfg:
            cfg.config = creds
            cfg.is_active = True
        else:
            cfg = IntegrationConfig(org_id=org_id, provider="salesforce", config=creds)
            db.add(cfg)
        await db.commit()
        return {"connected": True, "instance_url": instance}
    except HTTPException:
        raise
    except Exception as e:
        log.error("salesforce_connect failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/integrations/salesforce/disconnect")
async def salesforce_disconnect(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "salesforce")
        if cfg:
            cfg.is_active = False
            cfg.config = {}
            await db.commit()
        return {"disconnected": True}
    except Exception as e:
        log.error("salesforce_disconnect failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/integrations/salesforce/status", response_model=StatusOut)
async def salesforce_status(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "salesforce")
        if not cfg:
            return StatusOut(provider="salesforce", connected=False, is_active=False,
                             last_sync_at=None, last_sync_status=None)
        return StatusOut(
            provider="salesforce", connected=cfg.is_active, is_active=cfg.is_active,
            last_sync_at=cfg.last_sync_at.isoformat() if cfg.last_sync_at else None,
            last_sync_status=cfg.last_sync_status,
        )
    except Exception as e:
        log.error("salesforce_status failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/integrations/salesforce/sync-customers", response_model=SyncResult)
async def salesforce_sync_customers(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "salesforce")
        if not cfg or not cfg.is_active:
            raise HTTPException(status_code=422, detail="Salesforce not connected")
        instance = cfg.config.get("instance_url")
        token = cfg.config.get("access_token")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        customers = await db.execute(
            select(Customer).where(Customer.org_id == org_id, Customer.deleted_at.is_(None))
        )
        pushed = skipped = errors = 0

        async with httpx.AsyncClient(timeout=30) as client:
            for customer in customers.scalars():
                try:
                    r = await client.post(
                        f"{instance}/services/data/{SALESFORCE_API_VERSION}/sobjects/Account",
                        json={"Name": customer.company_name or "Unknown"},
                        headers=headers,
                    )
                    if r.status_code in (200, 201):
                        pushed += 1
                    else:
                        errors += 1
                except Exception:
                    errors += 1

        cfg.last_sync_at = datetime.now(timezone.utc)
        cfg.last_sync_status = "success" if errors == 0 else "partial"
        await db.commit()

        return SyncResult(pushed=pushed, skipped=skipped, errors=errors,
                          message=f"Pushed {pushed} accounts to Salesforce")
    except HTTPException:
        raise
    except Exception as e:
        log.error("salesforce_sync_customers failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/integrations/salesforce/sync-deals", response_model=SyncResult)
async def salesforce_sync_deals(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "salesforce")
        if not cfg or not cfg.is_active:
            raise HTTPException(status_code=422, detail="Salesforce not connected")
        instance = cfg.config.get("instance_url")
        token = cfg.config.get("access_token")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        deals = await db.execute(select(Deal).where(Deal.org_id == org_id))
        pushed = skipped = errors = 0

        async with httpx.AsyncClient(timeout=30) as client:
            for deal in deals.scalars():
                try:
                    close_date = deal.expected_close_date.strftime("%Y-%m-%d") if deal.expected_close_date else "2099-12-31"
                    r = await client.post(
                        f"{instance}/services/data/{SALESFORCE_API_VERSION}/sobjects/Opportunity",
                        json={
                            "Name": deal.title,
                            "Amount": float(deal.value or 0),
                            "StageName": deal.stage or "Prospecting",
                            "CloseDate": close_date,
                        },
                        headers=headers,
                    )
                    if r.status_code in (200, 201):
                        pushed += 1
                    else:
                        errors += 1
                except Exception:
                    errors += 1

        cfg.last_sync_at = datetime.now(timezone.utc)
        cfg.last_sync_status = "success" if errors == 0 else "partial"
        await db.commit()

        return SyncResult(pushed=pushed, skipped=skipped, errors=errors,
                          message=f"Pushed {pushed} opportunities to Salesforce")
    except HTTPException:
        raise
    except Exception as e:
        log.error("salesforce_sync_deals failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
