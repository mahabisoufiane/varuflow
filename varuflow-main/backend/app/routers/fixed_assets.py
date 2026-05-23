"""Fixed Asset Register router.

Endpoints:
  GET    /api/accounting/assets                        list all assets
  POST   /api/accounting/assets                        create asset
  GET    /api/accounting/assets/{id}                   get single asset with depreciation history
  PATCH  /api/accounting/assets/{id}                   update name/notes/account_code/supplier
  POST   /api/accounting/assets/{id}/depreciate        run depreciation for a period
  POST   /api/accounting/assets/{id}/dispose           mark disposed, record proceeds
  POST   /api/accounting/assets/{id}/revalue           revaluation entry (adjust book value)
  GET    /api/accounting/assets/{id}/schedule          depreciation table to end of life
  GET    /api/accounting/assets/report/schedule        org-wide depreciation schedule (date range)
  GET    /api/accounting/assets/export/sie4            SIE4 file of posted depreciation entries
"""
from __future__ import annotations

import io
import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.fixed_assets import AssetDepreciation, FixedAsset
from app.models.organization import OrgRole
from app.services.audit import log_action
from app.services import ledger as ledger_svc

router = APIRouter(prefix="/api/accounting/assets", tags=["fixed_assets"])
log = logging.getLogger(__name__)


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _actor(ctx: tuple) -> uuid.UUID:
    user, _ = ctx
    return user["user_id"]


def _require_owner_or_admin(ctx: tuple) -> None:
    _, member = ctx
    if member.role not in (OrgRole.OWNER, OrgRole.ADMIN):
        raise HTTPException(status_code=403, detail="Owner or admin required")


# ─── Schemas ──────────────────────────────────────────────────────────────

class AssetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category: str = Field(default="EQUIPMENT")  # BUILDING|EQUIPMENT|VEHICLE|IP|OTHER
    acquisition_date: date
    acquisition_cost: Decimal = Field(..., gt=0)
    salvage_value: Decimal = Field(default=Decimal("0"), ge=0)
    useful_life_years: int = Field(..., gt=0, le=100)
    depreciation_method: str = Field(default="STRAIGHT_LINE")  # STRAIGHT_LINE|DECLINING_BALANCE
    account_code: str = Field(default="1710", max_length=10)
    notes: Optional[str] = None
    supplier: Optional[str] = Field(None, max_length=200)
    purchase_order_id: Optional[uuid.UUID] = None
    expense_id: Optional[uuid.UUID] = None


class AssetPatch(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    notes: Optional[str] = None
    account_code: Optional[str] = Field(None, max_length=10)
    supplier: Optional[str] = Field(None, max_length=200)


class DepreciationOut(BaseModel):
    id: uuid.UUID
    period: date
    amount: Decimal
    journal_entry_id: Optional[uuid.UUID]
    created_at: datetime

    model_config = {"from_attributes": True}


class AssetOut(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    acquisition_date: date
    acquisition_cost: Decimal
    salvage_value: Decimal
    useful_life_years: int
    depreciation_method: str
    current_book_value: Decimal
    account_code: str
    notes: Optional[str]
    supplier: Optional[str]
    purchase_order_id: Optional[uuid.UUID]
    expense_id: Optional[uuid.UUID]
    is_disposed: bool
    disposed_at: Optional[date]
    disposal_proceeds: Optional[Decimal]
    created_at: datetime
    depreciations: list[DepreciationOut] = []

    model_config = {"from_attributes": True}


class ScheduleLine(BaseModel):
    period: date
    depreciation: Decimal
    book_value_after: Decimal


class OrgScheduleLine(BaseModel):
    asset_id: uuid.UUID
    asset_name: str
    category: str
    period: date
    depreciation: Decimal
    book_value_after: Decimal


class DisposeIn(BaseModel):
    disposed_at: date
    disposal_proceeds: Decimal = Field(default=Decimal("0"), ge=0)


class RevalueIn(BaseModel):
    revaluation_date: date
    new_book_value: Decimal = Field(..., ge=0)
    reason: Optional[str] = Field(None, max_length=300)


# ─── Helpers ──────────────────────────────────────────────────────────────

def _advance_month(d: date) -> date:
    if d.month == 12:
        return d.replace(year=d.year + 1, month=1)
    return d.replace(month=d.month + 1)


def _compute_period_depreciation(asset: FixedAsset, current_book_value: Optional[Decimal] = None) -> Decimal:
    """Monthly depreciation amount per method."""
    cost     = Decimal(str(asset.acquisition_cost))
    salvage  = Decimal(str(asset.salvage_value))
    bv       = current_book_value if current_book_value is not None else Decimal(str(asset.current_book_value))

    if asset.depreciation_method == "DECLINING_BALANCE":
        # Annual rate = 2 / useful_life; monthly = annual / 12
        annual_rate = Decimal("2") / Decimal(str(asset.useful_life_years))
        monthly = (bv * annual_rate / Decimal("12")).quantize(Decimal("0.01"))
    else:
        # Straight-line: (cost - salvage) / (years * 12)
        depreciable = cost - salvage
        monthly = (depreciable / (Decimal(str(asset.useful_life_years)) * 12)).quantize(Decimal("0.01"))

    return monthly


def _build_schedule(asset: FixedAsset) -> list[ScheduleLine]:
    """Full schedule from acquisition date to end of useful life."""
    total_months = asset.useful_life_years * 12
    book_val = Decimal(str(asset.acquisition_cost))
    salvage  = Decimal(str(asset.salvage_value))
    current  = asset.acquisition_date.replace(day=1)
    schedule = []

    for _ in range(total_months):
        remaining = book_val - salvage
        if remaining <= 0:
            break
        dep = min(_compute_period_depreciation(asset, book_val), remaining)
        book_val -= dep
        schedule.append(ScheduleLine(period=current, depreciation=dep, book_value_after=book_val))
        current = _advance_month(current)

    return schedule


# ─── Endpoints ────────────────────────────────────────────────────────────

@router.get("/report/depreciation-schedule", response_model=list[OrgScheduleLine])
async def org_depreciation_schedule(
    from_date: date = Query(...),
    to_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """Org-wide depreciation schedule for all active assets within a date range."""
    try:
        org_id = _org(ctx)
        assets = (
            await db.execute(
                select(FixedAsset)
                .where(FixedAsset.org_id == org_id, FixedAsset.is_disposed == False)  # noqa
            )
        ).scalars().all()

        result: list[OrgScheduleLine] = []
        for asset in assets:
            schedule = _build_schedule(asset)
            for line in schedule:
                if from_date <= line.period <= to_date:
                    result.append(OrgScheduleLine(
                        asset_id=asset.id,
                        asset_name=asset.name,
                        category=asset.category,
                        period=line.period,
                        depreciation=line.depreciation,
                        book_value_after=line.book_value_after,
                    ))

        result.sort(key=lambda r: (r.period, r.asset_name))
        return result
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"org_depreciation_schedule failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/export/sie4")
async def export_sie4(
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """Export posted depreciation entries as a SIE4 file."""
    try:
        org_id = _org(ctx)

        q = (
            select(AssetDepreciation, FixedAsset)
            .join(FixedAsset, AssetDepreciation.asset_id == FixedAsset.id)
            .where(FixedAsset.org_id == org_id)
        )
        if from_date:
            q = q.where(AssetDepreciation.period >= from_date)
        if to_date:
            q = q.where(AssetDepreciation.period <= to_date)
        q = q.order_by(AssetDepreciation.period)

        rows = (await db.execute(q)).all()

        buf = io.StringIO()
        gen_date = date.today().strftime("%Y%m%d")
        buf.write(f"#FLAGGA 0\n")
        buf.write(f"#FORMAT PC8\n")
        buf.write(f"#SIE 4\n")
        buf.write(f'#PROGRAM "Varuflow" 1.0\n')
        buf.write(f"#GEN {gen_date}\n")
        buf.write(f'#FNAMN ""\n')
        buf.write(f"#KPTYP EUBAS97\n\n")

        for i, (dep, asset) in enumerate(rows, start=1):
            period_str = dep.period.strftime("%Y%m%d")
            desc = f"Avskrivning {asset.name} {dep.period.strftime('%Y-%m')}"
            debit  = dep.amount.quantize(Decimal("0.01"))
            credit = debit
            buf.write(f'#VER A {i} {period_str} "{desc}"\n')
            buf.write("{\n")
            buf.write(f'  #TRANS 7830 {{}} {debit} "" "" ""\n')
            buf.write(f'  #TRANS {asset.account_code} {{}} -{credit} "" "" ""\n')
            buf.write("}\n")

        content = buf.getvalue()
        filename = f"depreciation_sie4_{gen_date}.se"
        return Response(
            content=content.encode("latin-1", errors="replace"),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"export_sie4 failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=list[AssetOut])
async def list_assets(
    include_disposed: bool = False,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    try:
        org_id = _org(ctx)
        q = select(FixedAsset).where(FixedAsset.org_id == org_id)
        if not include_disposed:
            q = q.where(FixedAsset.is_disposed == False)  # noqa
        q = q.options(selectinload(FixedAsset.depreciations)).order_by(FixedAsset.acquisition_date.desc())
        rows = (await db.execute(q)).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_assets failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=AssetOut, status_code=201)
async def create_asset(
    body: AssetCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)
        asset = FixedAsset(
            org_id=org_id,
            name=body.name,
            category=body.category,
            acquisition_date=body.acquisition_date,
            acquisition_cost=body.acquisition_cost,
            salvage_value=body.salvage_value,
            useful_life_years=body.useful_life_years,
            depreciation_method=body.depreciation_method,
            current_book_value=body.acquisition_cost,
            account_code=body.account_code,
            notes=body.notes,
            supplier=body.supplier,
            purchase_order_id=body.purchase_order_id,
            expense_id=body.expense_id,
        )
        db.add(asset)
        await db.commit()
        await db.refresh(asset)
        await log_action(db, action="asset.created", org_id=org_id,
                         actor_user_id=_actor(ctx), target_type="asset",
                         target_id=asset.id, request=request)
        await db.commit()
        return asset
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_asset failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{asset_id}", response_model=AssetOut)
async def get_asset(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    try:
        org_id = _org(ctx)
        asset = (
            await db.execute(
                select(FixedAsset)
                .where(FixedAsset.id == asset_id, FixedAsset.org_id == org_id)
                .options(selectinload(FixedAsset.depreciations))
            )
        ).scalar_one_or_none()
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        return asset
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"get_asset failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{asset_id}", response_model=AssetOut)
async def patch_asset(
    asset_id: uuid.UUID,
    body: AssetPatch,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)
        asset = (
            await db.execute(select(FixedAsset).where(FixedAsset.id == asset_id, FixedAsset.org_id == org_id))
        ).scalar_one_or_none()
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        if body.name:                    asset.name = body.name
        if body.notes is not None:       asset.notes = body.notes
        if body.account_code:            asset.account_code = body.account_code
        if body.supplier is not None:    asset.supplier = body.supplier
        await db.commit()
        await db.refresh(asset)
        return asset
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"patch_asset failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{asset_id}/depreciate", response_model=DepreciationOut, status_code=201)
async def run_depreciation(
    asset_id: uuid.UUID,
    request: Request,
    period: str = Query(..., description="YYYY-MM — period to depreciate"),
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """Run depreciation for one monthly period. Idempotent per period."""
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)

        try:
            period_date = date.fromisoformat(f"{period}-01")
        except ValueError:
            raise HTTPException(status_code=422, detail="period must be YYYY-MM")

        asset = (
            await db.execute(select(FixedAsset).where(FixedAsset.id == asset_id, FixedAsset.org_id == org_id))
        ).scalar_one_or_none()
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        if asset.is_disposed:
            raise HTTPException(status_code=409, detail="Asset is disposed")

        # Idempotency check
        existing = (
            await db.execute(
                select(AssetDepreciation).where(
                    AssetDepreciation.asset_id == asset_id,
                    AssetDepreciation.period == period_date,
                )
            )
        ).scalar_one_or_none()
        if existing:
            return existing

        bv = Decimal(str(asset.current_book_value))
        salvage = Decimal(str(asset.salvage_value))
        remaining = bv - salvage
        if remaining <= 0:
            raise HTTPException(status_code=409, detail="Asset is fully depreciated")

        dep_amount = min(_compute_period_depreciation(asset, bv), remaining)

        from app.models.accounting import JournalEntry, JournalLine
        entry = JournalEntry(
            org_id=org_id,
            entry_date=period_date,
            description=f"Depreciation: {asset.name} ({period})",
            source_type="ASSET_DEP",
            source_id=None,
            reference=str(asset.id)[:8],
            is_posted=True,
            created_by=_actor(ctx),
        )
        db.add(entry)
        await db.flush()
        db.add(JournalLine(journal_entry_id=entry.id, account_code="7830", debit=dep_amount, credit=Decimal("0"), memo=asset.name))
        db.add(JournalLine(journal_entry_id=entry.id, account_code=asset.account_code, debit=Decimal("0"), credit=dep_amount, memo=asset.name))

        dep_row = AssetDepreciation(
            asset_id=asset.id,
            period=period_date,
            amount=dep_amount,
            journal_entry_id=entry.id,
        )
        db.add(dep_row)

        asset.current_book_value = bv - dep_amount

        await db.commit()
        await db.refresh(dep_row)
        await log_action(db, action="asset.depreciated", org_id=org_id,
                         actor_user_id=_actor(ctx), target_type="asset", target_id=asset.id,
                         request=request, extra={"period": period, "amount": str(dep_amount)})
        await db.commit()
        return dep_row
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"run_depreciation failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{asset_id}/dispose", response_model=AssetOut)
async def dispose_asset(
    asset_id: uuid.UUID,
    body: DisposeIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """Mark an asset as disposed. Posts gain/loss journal entry."""
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)
        asset = (
            await db.execute(select(FixedAsset).where(FixedAsset.id == asset_id, FixedAsset.org_id == org_id))
        ).scalar_one_or_none()
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        if asset.is_disposed:
            raise HTTPException(status_code=409, detail="Asset already disposed")

        book_value = Decimal(str(asset.current_book_value))
        proceeds   = body.disposal_proceeds
        gain_loss  = proceeds - book_value

        from app.models.accounting import JournalEntry, JournalLine
        lines = []
        if proceeds > 0:
            lines.append(JournalLine(account_code="1920", debit=proceeds, credit=Decimal("0"), memo=f"Disposal proceeds: {asset.name}"))
        if book_value > 0:
            lines.append(JournalLine(account_code=asset.account_code, debit=Decimal("0"), credit=book_value, memo=f"Remove asset: {asset.name}"))
        if gain_loss > 0:
            lines.append(JournalLine(account_code="3000", debit=Decimal("0"), credit=gain_loss, memo=f"Gain on disposal: {asset.name}"))
        elif gain_loss < 0:
            lines.append(JournalLine(account_code="4000", debit=abs(gain_loss), credit=Decimal("0"), memo=f"Loss on disposal: {asset.name}"))

        if lines:
            entry = JournalEntry(
                org_id=org_id,
                entry_date=body.disposed_at,
                description=f"Asset disposal: {asset.name}",
                source_type="ASSET_DISPOSAL",
                reference=str(asset.id)[:8],
                is_posted=True,
                created_by=_actor(ctx),
            )
            db.add(entry)
            await db.flush()
            for ln in lines:
                ln.journal_entry_id = entry.id
                db.add(ln)

        asset.is_disposed = True
        asset.disposed_at = body.disposed_at
        asset.disposal_proceeds = proceeds
        asset.current_book_value = Decimal("0")

        await db.commit()
        await db.refresh(asset)
        await log_action(db, action="asset.disposed", org_id=org_id,
                         actor_user_id=_actor(ctx), target_type="asset", target_id=asset.id,
                         request=request, extra={"proceeds": str(proceeds)})
        await db.commit()
        return asset
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"dispose_asset failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{asset_id}/revalue", response_model=AssetOut)
async def revalue_asset(
    asset_id: uuid.UUID,
    body: RevalueIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """Record a revaluation: adjust book value up or down with a journal entry."""
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)
        asset = (
            await db.execute(select(FixedAsset).where(FixedAsset.id == asset_id, FixedAsset.org_id == org_id))
        ).scalar_one_or_none()
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        if asset.is_disposed:
            raise HTTPException(status_code=409, detail="Cannot revalue a disposed asset")

        old_bv = Decimal(str(asset.current_book_value))
        new_bv = body.new_book_value
        diff   = new_bv - old_bv  # positive = upward, negative = downward

        if diff == 0:
            raise HTTPException(status_code=422, detail="New book value is equal to current book value")

        from app.models.accounting import JournalEntry, JournalLine
        memo = body.reason or f"Revaluation: {asset.name}"
        # Up: debit asset account, credit revaluation reserve (3900)
        # Down: debit revaluation loss (7900), credit asset account
        entry = JournalEntry(
            org_id=org_id,
            entry_date=body.revaluation_date,
            description=memo,
            source_type="ASSET_REVALUE",
            reference=str(asset.id)[:8],
            is_posted=True,
            created_by=_actor(ctx),
        )
        db.add(entry)
        await db.flush()

        if diff > 0:
            db.add(JournalLine(journal_entry_id=entry.id, account_code=asset.account_code, debit=diff,             credit=Decimal("0"), memo=memo))
            db.add(JournalLine(journal_entry_id=entry.id, account_code="3900",             debit=Decimal("0"),     credit=diff,         memo=memo))
        else:
            abs_diff = abs(diff)
            db.add(JournalLine(journal_entry_id=entry.id, account_code="7900",             debit=abs_diff,         credit=Decimal("0"), memo=memo))
            db.add(JournalLine(journal_entry_id=entry.id, account_code=asset.account_code, debit=Decimal("0"),     credit=abs_diff,     memo=memo))

        asset.current_book_value = new_bv

        await db.commit()
        await db.refresh(asset)
        await log_action(db, action="asset.revalued", org_id=org_id,
                         actor_user_id=_actor(ctx), target_type="asset", target_id=asset.id,
                         request=request, extra={"old_bv": str(old_bv), "new_bv": str(new_bv)})
        await db.commit()
        return asset
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"revalue_asset failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{asset_id}/schedule", response_model=list[ScheduleLine])
async def depreciation_schedule(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """Full depreciation schedule from acquisition to end of useful life."""
    try:
        org_id = _org(ctx)
        asset = (
            await db.execute(select(FixedAsset).where(FixedAsset.id == asset_id, FixedAsset.org_id == org_id))
        ).scalar_one_or_none()
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        return _build_schedule(asset)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"depreciation_schedule failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
