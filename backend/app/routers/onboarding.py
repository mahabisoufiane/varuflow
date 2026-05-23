"""Onboarding checklist + first-run wizard + setup health (v26+).

Endpoints
─────────
GET  /api/onboarding                    → current checklist progress
POST /api/onboarding/complete-step      → mark a checklist step done

POST /api/onboarding/wizard/org-setup   → save company basics (name, VAT,
                                          currency, fiscal year, country)
POST /api/onboarding/wizard/complete    → mark wizard done on the org row
GET  /api/onboarding/setup-health       → 0-100 setup health score with
                                          item-level breakdown + next steps
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.invoicing import Customer, Invoice
from app.models.inventory import Product as InventoryItem
from app.models.onboarding import OnboardingProgress
from app.models.organization import Organization, OrganizationMember

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])
log = logging.getLogger(__name__)

# ── Checklist ─────────────────────────────────────────────────────────────────
# Ordered — ``next_step`` walks the list in this order.
ONBOARDING_STEPS: list[str] = [
    "ADD_FIRST_PRODUCT",
    "ADD_FIRST_CUSTOMER",
    "CREATE_FIRST_INVOICE",
    "INVITE_TEAM_MEMBER",
    "CONNECT_FORTNOX",
    "SEND_FIRST_INVOICE",
]
_STEP_SET = set(ONBOARDING_STEPS)


# ── Schemas ────────────────────────────────────────────────────────────────────

class CompleteStepIn(BaseModel):
    step: str


class OnboardingStatus(BaseModel):
    completed_steps: list[str]
    completion_pct: int
    next_step: str | None


class WizardOrgSetupIn(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    org_number: str | None = None
    vat_number: str | None = None
    address: str | None = None
    base_currency: str = Field(default="SEK", max_length=3)
    fiscal_year_start: int = Field(default=1, ge=1, le=12)
    country: str | None = Field(default=None, max_length=60)


class HealthItem(BaseModel):
    key: str
    label: str
    done: bool
    weight: int          # contribution to total score
    action_url: str | None = None


class SetupHealthOut(BaseModel):
    score: int           # 0–100
    items: list[HealthItem]
    next_steps: list[str]   # keys of the top 3 incomplete items


# ── Helpers ────────────────────────────────────────────────────────────────────

def _status_from_completed(completed: list[str]) -> OnboardingStatus:
    done = [s for s in ONBOARDING_STEPS if s in completed]
    pct = int(round(100 * len(done) / len(ONBOARDING_STEPS))) if ONBOARDING_STEPS else 0
    next_step = next((s for s in ONBOARDING_STEPS if s not in done), None)
    return OnboardingStatus(completed_steps=done, completion_pct=pct, next_step=next_step)


async def _load_completed(db: AsyncSession, org_id) -> list[str]:
    rows = (
        await db.execute(
            select(OnboardingProgress.step).where(OnboardingProgress.org_id == org_id)
        )
    ).scalars().all()
    return list(rows)


# ── Checklist endpoints ────────────────────────────────────────────────────────

@router.get("", response_model=OnboardingStatus)
async def get_status(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> OnboardingStatus:
    _, member = ctx
    try:
        completed = await _load_completed(db, member.org_id)
        return _status_from_completed(completed)
    except Exception as e:
        log.error("get_onboarding_status failed: %s", e, extra={"org_id": str(member.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/complete-step", response_model=OnboardingStatus)
async def complete_step(
    payload: CompleteStepIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> OnboardingStatus:
    _, member = ctx
    if payload.step not in _STEP_SET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown onboarding step: {payload.step}",
        )
    try:
        await db.execute(
            pg_insert(OnboardingProgress.__table__)
            .values(org_id=member.org_id, step=payload.step)
            .on_conflict_do_nothing(index_elements=["org_id", "step"])
        )
        await db.commit()
        completed = await _load_completed(db, member.org_id)
        return _status_from_completed(completed)
    except HTTPException:
        raise
    except Exception as e:
        log.error("complete_step failed: %s", e, extra={"org_id": str(member.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Wizard endpoints ───────────────────────────────────────────────────────────

@router.post("/wizard/org-setup")
async def wizard_org_setup(
    body: WizardOrgSetupIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Save company basics collected in wizard step 1/2."""
    _, member = ctx
    try:
        org = await db.scalar(
            select(Organization).where(Organization.id == member.org_id)
        )
        if not org:
            raise HTTPException(status_code=404, detail="Organisation not found")

        org.name = body.company_name.strip()
        if body.org_number is not None:
            org.org_number = body.org_number.strip() or None
        if body.vat_number is not None:
            org.vat_number = body.vat_number.strip() or None
        if body.address is not None:
            org.address = body.address.strip() or None
        org.base_currency = body.base_currency.upper()
        org.fiscal_year_start = body.fiscal_year_start

        await db.commit()
        return {
            "ok": True,
            "company_name": org.name,
            "base_currency": org.base_currency,
            "fiscal_year_start": org.fiscal_year_start,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("wizard_org_setup failed: %s", e, extra={"org_id": str(member.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/wizard/complete")
async def wizard_complete(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Mark the first-run wizard as done so it never re-appears."""
    _, member = ctx
    try:
        org = await db.scalar(
            select(Organization).where(Organization.id == member.org_id)
        )
        if org:
            org.onboarding_wizard_completed = True
            await db.commit()
        return {"ok": True, "wizard_completed": True}
    except Exception as e:
        log.error("wizard_complete failed: %s", e, extra={"org_id": str(member.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Setup health score ─────────────────────────────────────────────────────────

# Each item: (key, label, weight, action_url)
_HEALTH_ITEMS: list[tuple[str, str, int, str | None]] = [
    ("company_profile",    "Company profile complete",         15, "/settings"),
    ("currency_fiscal",    "Currency & fiscal year configured", 10, "/settings"),
    ("first_product",      "At least one product added",       15, "/inventory/new"),
    ("first_customer",     "At least one customer added",      15, "/customers/new"),
    ("first_invoice",      "First invoice created",            15, "/invoices/new"),
    ("team_member",        "Team member invited",              10, "/settings/team"),
    ("integration",        "Accounting integration connected", 10, "/settings/integrations"),
    ("opening_balances",   "Opening balances / chart of accounts set", 10, "/settings/accounting"),
]


@router.get("/setup-health", response_model=SetupHealthOut)
async def setup_health(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> SetupHealthOut:
    """Compute a 0–100 setup health score from live DB state."""
    _, member = ctx
    org_id = member.org_id
    try:
        # Load org
        org = await db.scalar(select(Organization).where(Organization.id == org_id))
        if not org:
            raise HTTPException(status_code=404, detail="Organisation not found")

        # Aggregate counts in parallel-ish queries
        product_count = (await db.scalar(
            select(func.count(InventoryItem.id)).where(InventoryItem.org_id == org_id)
        )) or 0
        customer_count = (await db.scalar(
            select(func.count(Customer.id)).where(Customer.org_id == org_id, Customer.is_active == True)  # noqa: E712
        )) or 0
        invoice_count = (await db.scalar(
            select(func.count(Invoice.id)).where(Invoice.org_id == org_id)
        )) or 0
        team_count = (await db.scalar(
            select(func.count(OrganizationMember.id)).where(OrganizationMember.org_id == org_id)
        )) or 0

        profile_done = bool(
            org.name and org.vat_number and org.address
        )
        currency_done = bool(
            org.base_currency and org.fiscal_year_start
        )
        integration_done = bool(org.fortnox_access_token)

        # Opening balances: proxy — if fiscal_year_start has been explicitly set away
        # from the default AND currency is non-SEK, treat as configured; otherwise
        # approximate via fortnox connection or product/customer having non-zero data.
        # A proper ledger balance check would need the ledger module — we use a heuristic.
        opening_done = integration_done or (product_count > 0 and invoice_count > 0)

        checks: dict[str, bool] = {
            "company_profile":  profile_done,
            "currency_fiscal":  currency_done,
            "first_product":    product_count > 0,
            "first_customer":   customer_count > 0,
            "first_invoice":    invoice_count > 0,
            "team_member":      team_count > 1,   # owner + at least 1 more
            "integration":      integration_done,
            "opening_balances": opening_done,
        }

        items: list[HealthItem] = []
        score = 0
        for key, label, weight, action_url in _HEALTH_ITEMS:
            done = checks.get(key, False)
            if done:
                score += weight
            items.append(HealthItem(key=key, label=label, done=done, weight=weight, action_url=action_url))

        next_steps = [i.key for i in items if not i.done][:3]
        return SetupHealthOut(score=score, items=items, next_steps=next_steps)
    except HTTPException:
        raise
    except Exception as e:
        log.error("setup_health failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")

