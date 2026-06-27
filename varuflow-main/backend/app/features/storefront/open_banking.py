"""Open Banking via Nordigen/GoCardless + Tink stub

Nordigen (now GoCardless Open Banking): real consent flow
Tink: stub (requires Tink developer account per customer)

Endpoints:
  GET  /api/integrations/open-banking/providers
  POST /api/integrations/open-banking/connect
  GET  /api/integrations/open-banking/callback   (no auth — receives bank consent redirect)
  GET  /api/integrations/open-banking/accounts
  POST /api/integrations/open-banking/accounts/{account_id}/import
  DELETE /api/integrations/open-banking/disconnect

  POST /api/integrations/tink/connect   (stub)
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_plan
from app.features.integrations.bank_feed_models import BankAccount, BankTransaction
from app.features.integrations.models import IntegrationConfig
from app.features.auth.organization import OrgPlan

router = APIRouter(tags=["integrations_banking"])
log = logging.getLogger(__name__)

NORDIGEN_API = "https://bankaccountdata.gocardless.com/api/v2"
PROVIDER = "nordigen"

# Sample institution list (subset — production fetches from /institutions/ endpoint)
SAMPLE_INSTITUTIONS = [
    {"id": "SEB_SESEBXXX", "name": "SEB", "countries": ["SE"], "logo": "https://cdn.nordigen.com/ais/SEB_SESEBXXX.png"},
    {"id": "SWEDBANK_SWEDSESS", "name": "Swedbank", "countries": ["SE"], "logo": "https://cdn.nordigen.com/ais/SWEDBANK_SWEDSESS.png"},
    {"id": "HANDELSBANKEN_HANDSESS", "name": "Handelsbanken", "countries": ["SE"], "logo": ""},
    {"id": "NORDEA_NDEAFIHHXXX", "name": "Nordea", "countries": ["SE", "FI", "NO", "DK"], "logo": ""},
    {"id": "DNB_DNBANOKKK", "name": "DNB", "countries": ["NO"], "logo": ""},
    {"id": "DANSKE_DABADKKK", "name": "Danske Bank", "countries": ["DK", "NO", "SE"], "logo": ""},
]


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


async def _nordigen_token(secret_id: str, secret_key: str) -> str:
    """Obtain Nordigen access token."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{NORDIGEN_API}/token/new/",
            json={"secret_id": secret_id, "secret_key": secret_key},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to obtain Nordigen access token")
    return resp.json()["access"]


# ── Schemas ───────────────────────────────────────────────────────────────────

class ConnectIn(BaseModel):
    institution_id: str
    country: str = "SE"

class ImportResult(BaseModel):
    imported: int
    skipped: int
    errors: int
    message: str

class AccountOut(BaseModel):
    id: str
    iban: Optional[str]
    name: Optional[str]
    currency: Optional[str]

class AccountsOut(BaseModel):
    accounts: list[AccountOut]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/api/integrations/open-banking/providers")
async def list_providers(
    country: Optional[str] = Query(None),
    ctx: tuple = Depends(get_current_member),
):
    """Return supported bank institutions (subset). Production fetches live from Nordigen."""
    institutions = SAMPLE_INSTITUTIONS
    if country:
        institutions = [i for i in institutions if country.upper() in i.get("countries", [])]
    return {"institutions": institutions}


@router.post("/api/integrations/open-banking/connect")
async def open_banking_connect(
    body: ConnectIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    """Create Nordigen requisition → returns redirect_url for user to open in browser."""
    org_id = _org(ctx)
    try:
        secret_id = os.getenv("NORDIGEN_SECRET_ID", "")
        secret_key = os.getenv("NORDIGEN_SECRET_KEY", "")
        if not secret_id or not secret_key:
            raise HTTPException(
                status_code=422,
                detail="NORDIGEN_SECRET_ID and NORDIGEN_SECRET_KEY must be configured. Obtain them at https://bankaccountdata.gocardless.com/",
            )

        frontend_url = os.getenv("FRONTEND_URL", "https://varuflow.vercel.app")
        redirect = f"{frontend_url}/integrations/banking?status=connected"
        token = await _nordigen_token(secret_id, secret_key)

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{NORDIGEN_API}/requisitions/",
                json={
                    "institution_id": body.institution_id,
                    "redirect": redirect,
                    "reference": str(org_id),
                },
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code not in (200, 201):
            raise HTTPException(status_code=502, detail=f"Nordigen error: {resp.status_code}")

        data = resp.json()
        requisition_id = data["id"]
        redirect_url = data["link"]

        cfg = await _get_config(db, org_id, PROVIDER)
        config = {"requisition_id": requisition_id, "institution_id": body.institution_id, "country": body.country}
        if cfg:
            cfg.config = config
            cfg.is_active = False  # not yet confirmed
        else:
            cfg = IntegrationConfig(org_id=org_id, provider=PROVIDER, config=config, is_active=False)
            db.add(cfg)
        await db.commit()

        return {"redirect_url": redirect_url, "requisition_id": requisition_id}
    except HTTPException:
        raise
    except Exception as e:
        log.error("open_banking_connect failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/integrations/open-banking/callback")
async def open_banking_callback(
    ref: Optional[str] = Query(None),    # org_id sent as reference
    error: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Auth-free callback after user completes bank consent. Fetches accounts from requisition."""
    try:
        if error or not ref:
            log.warning("open_banking_callback: error=%s ref=%s", error, ref)
            return {"status": "error", "message": error or "Missing ref"}

        try:
            org_id = uuid.UUID(ref)
        except ValueError:
            return {"status": "error", "message": "Invalid ref"}

        cfg = await _get_config(db, org_id, PROVIDER)
        if not cfg:
            return {"status": "error", "message": "No pending requisition for this org"}

        secret_id = os.getenv("NORDIGEN_SECRET_ID", "")
        secret_key = os.getenv("NORDIGEN_SECRET_KEY", "")
        token = await _nordigen_token(secret_id, secret_key)

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{NORDIGEN_API}/requisitions/{cfg.config['requisition_id']}/",
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code != 200:
            return {"status": "error"}

        accounts = resp.json().get("accounts", [])
        cfg.config = {**cfg.config, "accounts": accounts}
        cfg.is_active = True
        await db.commit()

        return {"status": "connected", "accounts": len(accounts)}
    except Exception as e:
        log.error("open_banking_callback failed: %s", str(e))
        return {"status": "error", "message": "Internal error"}


@router.get("/api/integrations/open-banking/accounts", response_model=AccountsOut)
async def list_accounts(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, PROVIDER)
        if not cfg or not cfg.is_active:
            return AccountsOut(accounts=[])

        accounts_raw = cfg.config.get("accounts", [])
        if not accounts_raw:
            return AccountsOut(accounts=[])

        secret_id = os.getenv("NORDIGEN_SECRET_ID", "")
        secret_key = os.getenv("NORDIGEN_SECRET_KEY", "")
        token = await _nordigen_token(secret_id, secret_key)

        result = []
        async with httpx.AsyncClient(timeout=15) as client:
            for acc_id in accounts_raw:
                try:
                    resp = await client.get(
                        f"{NORDIGEN_API}/accounts/{acc_id}/details/",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if resp.status_code == 200:
                        det = resp.json().get("account", {})
                        result.append(AccountOut(
                            id=acc_id,
                            iban=det.get("iban"),
                            name=det.get("name") or det.get("ownerName"),
                            currency=det.get("currency"),
                        ))
                except Exception:
                    pass

        return AccountsOut(accounts=result)
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_accounts failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/integrations/open-banking/accounts/{account_id}/import", response_model=ImportResult)
async def import_transactions(
    account_id: str,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, PROVIDER)
        if not cfg or not cfg.is_active:
            raise HTTPException(status_code=422, detail="Open Banking not connected")

        secret_id = os.getenv("NORDIGEN_SECRET_ID", "")
        secret_key = os.getenv("NORDIGEN_SECRET_KEY", "")
        token = await _nordigen_token(secret_id, secret_key)

        # Fetch or create BankAccount row
        bank_acc_row = await db.execute(
            select(BankAccount).where(
                BankAccount.org_id == org_id,
                BankAccount.external_account_id == account_id,
            )
        )
        bank_account = bank_acc_row.scalar_one_or_none()
        if not bank_account:
            bank_account = BankAccount(
                org_id=org_id,
                external_account_id=account_id,
                provider="nordigen",
                name=account_id,
            )
            db.add(bank_account)
            await db.flush()

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{NORDIGEN_API}/accounts/{account_id}/transactions/",
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Nordigen API error: {resp.status_code}")

        txns = resp.json().get("transactions", {}).get("booked", [])
        imported = skipped = errors = 0

        for txn in txns:
            try:
                amt = Decimal(str(txn.get("transactionAmount", {}).get("amount", "0")))
                txn_date_str = txn.get("bookingDate", txn.get("valueDate", ""))
                try:
                    txn_date = date.fromisoformat(txn_date_str)
                except Exception:
                    txn_date = date.today()
                desc = txn.get("remittanceInformationUnstructured", txn.get("transactionId", ""))

                # Check for duplicate (unique constraint on bank_account_id, transaction_date, amount, description)
                dup = await db.execute(
                    select(BankTransaction).where(
                        BankTransaction.bank_account_id == bank_account.id,
                        BankTransaction.transaction_date == txn_date,
                        BankTransaction.amount == amt,
                        BankTransaction.description == desc,
                    )
                )
                if dup.scalar_one_or_none():
                    skipped += 1
                    continue

                db.add(BankTransaction(
                    bank_account_id=bank_account.id,
                    transaction_date=txn_date,
                    amount=amt,
                    currency=txn.get("transactionAmount", {}).get("currency", "SEK"),
                    description=desc,
                ))
                imported += 1
            except Exception:
                errors += 1

        cfg.last_sync_at = datetime.now(timezone.utc)
        cfg.last_sync_status = "success" if errors == 0 else "partial"
        await db.commit()

        return ImportResult(imported=imported, skipped=skipped, errors=errors,
                            message=f"Imported {imported} transactions, {skipped} duplicates skipped")
    except HTTPException:
        raise
    except Exception as e:
        log.error("import_transactions failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/integrations/open-banking/disconnect")
async def open_banking_disconnect(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, PROVIDER)
        if cfg:
            cfg.is_active = False
            cfg.config = {}
            await db.commit()
        return {"disconnected": True}
    except Exception as e:
        log.error("open_banking_disconnect failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Tink stub ─────────────────────────────────────────────────────────────────

@router.post("/api/integrations/tink/connect")
async def tink_connect(
    ctx: tuple = Depends(get_current_member),
):
    """Tink requires a developer account per customer. Stub endpoint."""
    return {
        "status": "stub",
        "message": (
            "Tink integration requires a Tink developer account registered for your company. "
            "Apply at https://tink.com/developers/. Once approved, configure your Tink credentials "
            "and contact Varuflow support to enable live Tink sync."
        ),
    }
