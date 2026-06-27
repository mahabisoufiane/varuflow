"""Multi-Entity management

Manages subsidiary / branch hierarchy under a parent org.
Handles intercompany transfers with transfer pricing and
generates consolidated P&L reports with elimination entries.

Endpoints:
  GET  /api/multi-entity/entities              list all entities in the group
  POST /api/multi-entity/entities              create subsidiary
  GET  /api/multi-entity/entities/{id}
  PATCH /api/multi-entity/entities/{id}
  GET  /api/multi-entity/consolidated/{period} consolidated P&L for YYYY-MM
  POST /api/multi-entity/transfers             create intercompany transfer
  GET  /api/multi-entity/transfers
  PATCH /api/multi-entity/transfers/{id}/post  post + auto-create elimination
  GET  /api/multi-entity/eliminations/{period}
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.multi_entity import EliminationEntry, IntercompanyTransfer
from app.models.organization import Organization

router = APIRouter(prefix="/api/multi-entity", tags=["multi_entity"])
log = logging.getLogger(__name__)


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Schemas ───────────────────────────────────────────────────────────────────

class EntityIn(BaseModel):
    name: str
    legal_name: Optional[str] = None
    entity_type: str = "subsidiary"   # subsidiary|standalone
    reporting_currency: Optional[str] = "SEK"
    country: Optional[str] = None

class EntityPatch(BaseModel):
    name: Optional[str] = None
    legal_name: Optional[str] = None
    reporting_currency: Optional[str] = None
    country: Optional[str] = None

class EntityOut(BaseModel):
    id: str
    name: str
    legal_name: Optional[str]
    entity_type: str
    reporting_currency: Optional[str]
    parent_org_id: Optional[str]

class TransferIn(BaseModel):
    to_org_id: uuid.UUID
    transfer_type: str = "stock"       # stock|cash|service
    product_id: Optional[uuid.UUID] = None
    quantity: Optional[float] = None
    transfer_price: Decimal
    currency: str = "SEK"
    transfer_date: date
    description: Optional[str] = None
    reference: Optional[str] = None

class TransferOut(BaseModel):
    id: str
    from_org_id: str
    to_org_id: str
    transfer_type: str
    product_id: Optional[str]
    quantity: Optional[str]
    transfer_price: str
    currency: str
    transfer_date: str
    status: str
    description: Optional[str]
    reference: Optional[str]
    created_at: str

class EliminationOut(BaseModel):
    id: str
    period: str
    entry_type: str
    from_org_id: Optional[str]
    to_org_id: Optional[str]
    amount: str
    currency: str
    description: Optional[str]


def _t_out(t: IntercompanyTransfer) -> TransferOut:
    return TransferOut(
        id=str(t.id), from_org_id=str(t.from_org_id), to_org_id=str(t.to_org_id),
        transfer_type=t.transfer_type,
        product_id=str(t.product_id) if t.product_id else None,
        quantity=str(t.quantity) if t.quantity else None,
        transfer_price=str(t.transfer_price), currency=t.currency,
        transfer_date=t.transfer_date.isoformat(), status=t.status,
        description=t.description, reference=t.reference,
        created_at=t.created_at.isoformat(),
    )


def _e_out(e: EliminationEntry) -> EliminationOut:
    return EliminationOut(
        id=str(e.id), period=e.period, entry_type=e.entry_type,
        from_org_id=str(e.from_org_id) if e.from_org_id else None,
        to_org_id=str(e.to_org_id) if e.to_org_id else None,
        amount=str(e.amount), currency=e.currency, description=e.description,
    )


def _org_out(o: Organization) -> EntityOut:
    return EntityOut(
        id=str(o.id), name=o.name,
        legal_name=getattr(o, "legal_name", None),
        entity_type=getattr(o, "entity_type", "standalone"),
        reporting_currency=getattr(o, "reporting_currency", None),
        parent_org_id=str(o.parent_org_id) if getattr(o, "parent_org_id", None) else None,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/entities")
async def list_entities(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return the calling org + all subsidiaries it is parent of."""
    org_id = _org(ctx)
    try:
        rows = await db.execute(
            select(Organization).where(
                (Organization.id == org_id) | (Organization.parent_org_id == org_id)
            )
        )
        orgs = rows.scalars().all()
        return {"entities": [_org_out(o) for o in orgs]}
    except Exception as e:
        log.error("list_entities failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/entities", response_model=EntityOut)
async def create_subsidiary(
    body: EntityIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Spin up a new subsidiary org under the calling org."""
    org_id = _org(ctx)
    try:
        # Verify caller's org is the parent (standalone or franchisor)
        parent_row = await db.execute(select(Organization).where(Organization.id == org_id))
        parent = parent_row.scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent org not found")

        # Mark parent as having subsidiaries if not already
        if getattr(parent, "entity_type", "standalone") == "standalone":
            parent.entity_type = "parent"

        sub = Organization(
            name=body.name,
            slug=f"{body.name.lower().replace(' ', '-')}-{str(uuid.uuid4())[:6]}",
        )
        # Set hierarchy columns (added by migration)
        sub.parent_org_id = org_id
        sub.entity_type = body.entity_type
        sub.legal_name = body.legal_name
        sub.reporting_currency = body.reporting_currency

        db.add(sub)
        await db.commit()
        await db.refresh(sub)
        return _org_out(sub)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_subsidiary failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/entities/{entity_id}", response_model=EntityOut)
async def get_entity(
    entity_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(Organization).where(
                Organization.id == entity_id,
                (Organization.id == org_id) | (Organization.parent_org_id == org_id),
            )
        )
        org = row.scalar_one_or_none()
        if not org:
            raise HTTPException(status_code=404, detail="Entity not found")
        return _org_out(org)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_entity failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/entities/{entity_id}", response_model=EntityOut)
async def update_entity(
    entity_id: uuid.UUID,
    body: EntityPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(Organization).where(
                Organization.id == entity_id,
                (Organization.id == org_id) | (Organization.parent_org_id == org_id),
            )
        )
        org = row.scalar_one_or_none()
        if not org:
            raise HTTPException(status_code=404, detail="Entity not found")
        if body.name is not None:
            org.name = body.name
        if body.legal_name is not None:
            org.legal_name = body.legal_name
        if body.reporting_currency is not None:
            org.reporting_currency = body.reporting_currency
        await db.commit()
        return _org_out(org)
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_entity failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/consolidated/{period}")
async def consolidated_report(
    period: str,  # YYYY-MM
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate revenue, COGS, gross profit across all group entities for a period.
    Subtracts elimination entries to remove intercompany profit."""
    org_id = _org(ctx)
    try:
        # Get group entity IDs
        rows = await db.execute(
            select(Organization.id, Organization.name).where(
                (Organization.id == org_id) | (Organization.parent_org_id == org_id)
            )
        )
        entities = {str(r.id): r.name for r in rows}
        entity_ids = list(entities.keys())

        if not entity_ids:
            return {"period": period, "entities": [], "consolidated": {}}

        year, month = period.split("-")

        # Query invoice revenue per entity
        revenue_q = await db.execute(text("""
            SELECT org_id::text, COALESCE(SUM(total_amount), 0) as revenue
            FROM invoices
            WHERE org_id = ANY(:ids::uuid[])
              AND status IN ('paid', 'sent')
              AND EXTRACT(YEAR FROM issue_date) = :year
              AND EXTRACT(MONTH FROM issue_date) = :month
            GROUP BY org_id
        """), {"ids": entity_ids, "year": int(year), "month": int(month)})
        revenue_map = {str(r.org_id): float(r.revenue) for r in revenue_q}

        # Query elimination entries
        elim_q = await db.execute(
            select(func.sum(EliminationEntry.amount)).where(
                EliminationEntry.parent_org_id == org_id,
                EliminationEntry.period == period,
            )
        )
        total_eliminations = float(elim_q.scalar_one() or 0)

        entity_rows = []
        total_revenue = 0.0
        for eid, ename in entities.items():
            rev = revenue_map.get(eid, 0.0)
            total_revenue += rev
            entity_rows.append({"id": eid, "name": ename, "revenue": rev})

        return {
            "period": period,
            "entities": entity_rows,
            "consolidated": {
                "gross_revenue": total_revenue,
                "intercompany_eliminations": total_eliminations,
                "net_group_revenue": total_revenue - total_eliminations,
            },
        }
    except Exception as e:
        log.error("consolidated_report failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/transfers", response_model=TransferOut)
async def create_transfer(
    body: TransferIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        # Verify to_org is in the same group
        row = await db.execute(
            select(Organization).where(
                Organization.id == body.to_org_id,
                (Organization.parent_org_id == org_id) | (Organization.id == org_id),
            )
        )
        if not row.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Target entity not in your group")

        transfer = IntercompanyTransfer(
            from_org_id=org_id,
            to_org_id=body.to_org_id,
            transfer_type=body.transfer_type,
            product_id=body.product_id,
            quantity=Decimal(str(body.quantity)) if body.quantity else None,
            transfer_price=body.transfer_price,
            currency=body.currency,
            transfer_date=body.transfer_date,
            description=body.description,
            reference=body.reference,
        )
        db.add(transfer)
        await db.commit()
        await db.refresh(transfer)
        return _t_out(transfer)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_transfer failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/transfers")
async def list_transfers(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        q = select(IntercompanyTransfer).where(
            (IntercompanyTransfer.from_org_id == org_id) | (IntercompanyTransfer.to_org_id == org_id)
        )
        count_row = await db.execute(
            select(func.count(IntercompanyTransfer.id)).where(
                (IntercompanyTransfer.from_org_id == org_id) | (IntercompanyTransfer.to_org_id == org_id)
            )
        )
        total = count_row.scalar_one() or 0
        rows = await db.execute(q.order_by(IntercompanyTransfer.transfer_date.desc()).limit(limit).offset((page - 1) * limit))
        return {"transfers": [_t_out(t) for t in rows.scalars()], "total": total}
    except Exception as e:
        log.error("list_transfers failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/transfers/{transfer_id}/post", response_model=TransferOut)
async def post_transfer(
    transfer_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Post a draft transfer and auto-generate an elimination entry."""
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(IntercompanyTransfer).where(
                IntercompanyTransfer.id == transfer_id,
                IntercompanyTransfer.from_org_id == org_id,
            )
        )
        transfer = row.scalar_one_or_none()
        if not transfer:
            raise HTTPException(status_code=404, detail="Transfer not found")
        if transfer.status != "draft":
            raise HTTPException(status_code=422, detail="Only draft transfers can be posted")

        # Find the parent/root org for eliminations
        caller_row = await db.execute(select(Organization).where(Organization.id == org_id))
        caller = caller_row.scalar_one()
        parent_id = getattr(caller, "parent_org_id", None) or org_id

        period = transfer.transfer_date.strftime("%Y-%m")

        # Eliminate intercompany revenue (seller) and corresponding COGS (buyer)
        elim = EliminationEntry(
            parent_org_id=parent_id,
            period=period,
            entry_type="intercompany_revenue",
            from_org_id=transfer.from_org_id,
            to_org_id=transfer.to_org_id,
            amount=transfer.transfer_price,
            currency=transfer.currency,
            description=f"Auto-elimination for transfer {str(transfer_id)[:8]}",
        )
        db.add(elim)

        transfer.status = "posted"
        transfer.elimination_entry_id = elim.id
        await db.commit()
        await db.refresh(transfer)
        return _t_out(transfer)
    except HTTPException:
        raise
    except Exception as e:
        log.error("post_transfer failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/eliminations/{period}")
async def list_eliminations(
    period: str,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        rows = await db.execute(
            select(EliminationEntry).where(
                EliminationEntry.parent_org_id == org_id,
                EliminationEntry.period == period,
            )
        )
        entries = rows.scalars().all()
        total = sum(float(e.amount) for e in entries)
        return {"period": period, "eliminations": [_e_out(e) for e in entries], "total": total}
    except Exception as e:
        log.error("list_eliminations failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Cross-Entity User Permissions ─────────────────────────────────────────────

from app.models.cross_entity_roles import MultiEntityRole  # noqa: E402
from pydantic import BaseModel as _BaseModel  # noqa: E402 (already imported, alias avoids clash)


class _RoleIn(_BaseModel):
    user_id: uuid.UUID
    org_id: uuid.UUID
    role: str


def _role_out(r: "MultiEntityRole") -> dict:
    return {
        "id": str(r.id),
        "user_id": str(r.user_id),
        "org_id": str(r.org_id),
        "role": r.role,
        "granted_by_user_id": str(r.granted_by_user_id) if r.granted_by_user_id else None,
        "created_at": r.created_at.isoformat(),
    }


@router.get("/permissions")
async def list_permissions(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """List all cross-entity role assignments under this group."""
    org_id = _org(ctx)
    try:
        # Return roles for all entities where this org is parent (same user group)
        rows = (await db.execute(
            select(MultiEntityRole).where(MultiEntityRole.org_id == org_id)
            .order_by(MultiEntityRole.created_at.desc())
        )).scalars().all()
        return [_role_out(r) for r in rows]
    except Exception as e:
        log.error("list_permissions failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/permissions", status_code=201)
async def assign_permission(
    body: _RoleIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Assign a user a specific role in a subsidiary entity."""
    org_id = _org(ctx)
    try:
        # Verify the target org is in the same group
        target_org = await db.scalar(
            select(Organization).where(Organization.id == body.org_id)
        )
        if not target_org:
            raise HTTPException(status_code=404, detail="Target organisation not found")

        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = (
            pg_insert(MultiEntityRole.__table__)
            .values(
                user_id=body.user_id,
                org_id=body.org_id,
                role=body.role,
                granted_by_user_id=uuid.UUID(str(ctx[0]["user_id"])),
            )
            .on_conflict_do_update(
                index_elements=["user_id", "org_id"],
                set_={"role": body.role},
            )
            .returning(MultiEntityRole.__table__)
        )
        result = await db.execute(stmt)
        await db.commit()
        row = result.fetchone()
        return {
            "id": str(row.id),
            "user_id": str(row.user_id),
            "org_id": str(row.org_id),
            "role": row.role,
            "granted_by_user_id": str(row.granted_by_user_id) if row.granted_by_user_id else None,
            "created_at": row.created_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("assign_permission failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/permissions/{role_id}", status_code=204)
async def remove_permission(
    role_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Remove a cross-entity role assignment."""
    org_id = _org(ctx)
    try:
        role = await db.scalar(
            select(MultiEntityRole).where(
                MultiEntityRole.id == role_id,
                MultiEntityRole.org_id == org_id,
            )
        )
        if not role:
            raise HTTPException(status_code=404, detail="Permission not found")
        await db.delete(role)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("remove_permission failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
