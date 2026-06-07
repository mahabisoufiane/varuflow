"""Supplier Portal router (Item 37) — read-only access to purchase
orders for suppliers plus a PO-acceptance (confirm) mutation.

Endpoints overview:

Admin (organization-scoped, ``get_current_member``):

* ``POST /api/supplier-portal/tokens`` — issue a token for a supplier,
  optionally email the magic link.  ``log_action("supplier_portal.token_issued")``.
* ``GET  /api/supplier-portal/tokens`` — list tokens for this org,
  optionally filtered to one supplier. Never returns the raw token.
* ``POST /api/supplier-portal/tokens/{token_id}/revoke`` — revoke a
  live token. ``log_action("supplier_portal.token_revoked")``.

Supplier (token-authenticated, ``get_portal_supplier`` dep below):

* ``GET  /api/supplier-portal/me`` — token-holder identity summary.
* ``GET  /api/supplier-portal/purchase-orders`` — open / past POs.
* ``GET  /api/supplier-portal/purchase-orders/{po_id}`` — detail.
* ``POST /api/supplier-portal/purchase-orders/{po_id}/confirm`` —
  supplier accepts the PO. ``log_action("supplier_portal.po_confirmed")``.

There are **no PATCH / PUT / DELETE** endpoints on this router. Price,
product, and line-item data are strictly read-only from the supplier's
side; the ``confirm`` POST is the single sanctioned mutation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.inventory import Supplier
from app.services import supplier_portal_service as svc
from app.services.audit import log_action
from app.services.email import send_supplier_portal_email

router = APIRouter(prefix="/api/supplier-portal", tags=["supplier-portal"], dependencies=[Depends(require_module("inventory"))])

_bearer = HTTPBearer(auto_error=True)


# ═══════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════


class TokenIssueIn(BaseModel):
    supplier_id: uuid.UUID
    expires_in_days: int = Field(default=svc.DEFAULT_EXPIRY_DAYS, ge=1, le=svc.MAX_EXPIRY_DAYS)
    # Default True — the whole point is to notify the supplier. Admins
    # can set False when they want to hand-deliver the link (e.g. via
    # Signal / existing support channel).
    send_email: bool = True


class TokenIssueOut(BaseModel):
    id: uuid.UUID
    supplier_id: uuid.UUID
    magic_url: str
    expires_at: datetime
    email_sent: bool
    # Dev helper — in prod this is always the same as ``magic_url`` so
    # we don't need to duplicate. Kept so integration tests have an
    # explicit signal that the happy-path URL was generated.
    raw_token_preview: str


class TokenOut(BaseModel):
    id: uuid.UUID
    supplier_id: uuid.UUID
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None
    is_revoked: bool
    is_live: bool


class POItemOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    quantity: int
    unit_price: str
    line_total: str


class POOut(BaseModel):
    id: uuid.UUID
    status: str
    total: str
    notes: str | None
    created_at: datetime
    confirmed_at: datetime | None
    items: list[POItemOut]


class MeOut(BaseModel):
    supplier_id: uuid.UUID
    supplier_name: str
    org_id: uuid.UUID
    token_expires_at: datetime


class ConfirmOut(BaseModel):
    po_id: uuid.UUID
    confirmed_at: datetime


# ═══════════════════════════════════════════════════════════════════
# Supplier-side auth dependency
# ═══════════════════════════════════════════════════════════════════


async def get_portal_supplier(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Resolve the bearer token to ``(supplier_id, org_id, token_id)``.

    Runs the same state-machine check as :func:`svc.validate_token_record`
    plus the hash lookup. On any failure raises 401 with a generic
    "Invalid or expired portal session" message so the supplier cannot
    distinguish "revoked" from "expired" from "never existed".
    """
    raw = credentials.credentials
    if not raw:
        raise HTTPException(status_code=401, detail="Invalid or expired portal session")

    row = await svc.lookup_by_raw_token(db, raw_token=raw)
    if row is None:
        raise HTTPException(status_code=401, detail="Invalid or expired portal session")

    record = svc.TokenRecord(
        supplier_id=row.supplier_id,
        org_id=row.org_id,
        token_hash=row.token_hash,
        created_at=row.created_at,
        expires_at=row.expires_at,
        last_used_at=row.last_used_at,
        is_revoked=row.is_revoked,
    )
    try:
        svc.validate_token_record(record, raw_token=raw, now=datetime.now(timezone.utc))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired portal session")

    # Touch last_used_at for admin visibility (fire-and-forget).
    await svc.touch_last_used(db, token_id=row.id)
    return row.supplier_id, row.org_id, row.id


# ═══════════════════════════════════════════════════════════════════
# Admin endpoints — issue / list / revoke
# ═══════════════════════════════════════════════════════════════════


@router.post("/tokens", response_model=TokenIssueOut, status_code=201)
async def issue_supplier_token(
    body: TokenIssueIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    supplier = await db.get(Supplier, body.supplier_id)
    if supplier is None or supplier.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="Supplier not found")
    if not supplier.is_active:
        raise HTTPException(status_code=400, detail="Supplier is inactive")

    raw_token, row = await svc.issue_token(
        db,
        supplier_id=supplier.id,
        org_id=member.org_id,
        expires_in_days=body.expires_in_days,
    )
    magic_url = svc.build_magic_url(settings.PORTAL_BASE_URL, raw_token)

    # Optionally email the supplier. Email failures do not abort
    # issuance — admin can hand-deliver the link from the response.
    email_sent = False
    if body.send_email and supplier.email:
        try:
            # Fetch org name for the template copy.
            from app.models.organization import Organization
            org = await db.get(Organization, member.org_id)
            org_name = org.name if org else "Varuflow"
            email_sent = await send_supplier_portal_email(
                to_email=supplier.email,
                supplier_name=supplier.name,
                magic_url=magic_url,
                org_name=org_name,
                expires_in_days=body.expires_in_days,
            )
        except Exception:
            email_sent = False

    await log_action(
        db,
        action="supplier_portal.token_issued",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="supplier_portal_token",
        target_id=str(row.id),
        request=request,
        extra={
            "supplier_id": str(supplier.id),
            "expires_in_days": body.expires_in_days,
            "email_sent": email_sent,
        },
    )
    await db.commit()
    await db.refresh(row)

    return TokenIssueOut(
        id=row.id,
        supplier_id=supplier.id,
        magic_url=magic_url,
        expires_at=row.expires_at,
        email_sent=email_sent,
        raw_token_preview=svc.mask_raw_token(raw_token),
    )


@router.get("/tokens", response_model=list[TokenOut])
async def list_supplier_tokens(
    supplier_id: uuid.UUID | None = Query(None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _user, member = ctx
    rows = await svc.find_active_tokens(
        db, org_id=member.org_id, supplier_id=supplier_id,
    )
    now = datetime.now(timezone.utc)
    return [
        TokenOut(
            id=r.id,
            supplier_id=r.supplier_id,
            created_at=r.created_at,
            expires_at=r.expires_at,
            last_used_at=r.last_used_at,
            is_revoked=r.is_revoked,
            is_live=svc.is_token_live(
                svc.TokenRecord(
                    supplier_id=r.supplier_id,
                    org_id=r.org_id,
                    token_hash=r.token_hash,
                    created_at=r.created_at,
                    expires_at=r.expires_at,
                    last_used_at=r.last_used_at,
                    is_revoked=r.is_revoked,
                ),
                now,
            ),
        )
        for r in rows
    ]


@router.post("/tokens/{token_id}/revoke", status_code=200)
async def revoke_supplier_token(
    token_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    changed = await svc.revoke_token(db, token_id=token_id, org_id=member.org_id)
    if not changed:
        raise HTTPException(status_code=404, detail="Token not found or already revoked")
    await log_action(
        db,
        action="supplier_portal.token_revoked",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="supplier_portal_token",
        target_id=str(token_id),
        request=request,
    )
    await db.commit()
    return {"status": "revoked"}


# ═══════════════════════════════════════════════════════════════════
# Supplier-side endpoints (READ-ONLY except confirm)
# ═══════════════════════════════════════════════════════════════════


@router.get("/me", response_model=MeOut)
async def portal_me(
    principal: tuple[uuid.UUID, uuid.UUID, uuid.UUID] = Depends(get_portal_supplier),
    db: AsyncSession = Depends(get_db),
):
    supplier_id, org_id, token_id = principal
    supplier = await db.get(Supplier, supplier_id)
    if supplier is None or supplier.org_id != org_id:
        # Supplier deleted since token issued — treat as unauthorised.
        raise HTTPException(status_code=401, detail="Invalid or expired portal session")
    from app.models.supplier_portal import SupplierPortalToken
    token_row = await db.get(SupplierPortalToken, token_id)
    return MeOut(
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        org_id=org_id,
        token_expires_at=token_row.expires_at if token_row else datetime.now(timezone.utc),
    )


@router.get("/purchase-orders", response_model=list[POOut])
async def list_supplier_purchase_orders(
    principal: tuple[uuid.UUID, uuid.UUID, uuid.UUID] = Depends(get_portal_supplier),
    db: AsyncSession = Depends(get_db),
):
    supplier_id, org_id, _ = principal
    rows = await svc.list_supplier_pos(db, supplier_id=supplier_id, org_id=org_id)
    return [_po_to_out(p) for p in rows]


@router.get("/purchase-orders/{po_id}", response_model=POOut)
async def get_supplier_purchase_order(
    po_id: uuid.UUID,
    principal: tuple[uuid.UUID, uuid.UUID, uuid.UUID] = Depends(get_portal_supplier),
    db: AsyncSession = Depends(get_db),
):
    supplier_id, org_id, _ = principal
    po = await svc.get_supplier_po(
        db, po_id=po_id, supplier_id=supplier_id, org_id=org_id,
    )
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return _po_to_out(po)


@router.post("/purchase-orders/{po_id}/confirm", response_model=ConfirmOut)
async def confirm_supplier_purchase_order(
    po_id: uuid.UUID,
    request: Request,
    principal: tuple[uuid.UUID, uuid.UUID, uuid.UUID] = Depends(get_portal_supplier),
    db: AsyncSession = Depends(get_db),
):
    supplier_id, org_id, token_id = principal
    # Verify the PO exists + belongs to this supplier *before* the
    # atomic UPDATE so we can 404 vs 409 cleanly.
    po = await svc.get_supplier_po(
        db, po_id=po_id, supplier_id=supplier_id, org_id=org_id,
    )
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    # Pure-level guard (ensures bad router changes can't bypass the
    # supplier-ownership / already-confirmed checks silently).
    try:
        svc.can_confirm_po(
            po_supplier_id=po.supplier_id,
            requesting_supplier_id=supplier_id,
            confirmed_at=po.confirmed_at,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "po_already_confirmed":
            raise HTTPException(status_code=409, detail=code)
        raise HTTPException(status_code=403, detail=code)

    changed = await svc.confirm_po(
        db, po_id=po_id, supplier_id=supplier_id, org_id=org_id,
    )
    if not changed:
        # Lost a race with a concurrent confirm. The PO is now
        # confirmed by the other actor; treat as idempotent-conflict.
        raise HTTPException(status_code=409, detail="po_already_confirmed")

    await log_action(
        db,
        action="supplier_portal.po_confirmed",
        org_id=org_id,
        # Portal guests have no backing user row — None is the
        # documented value for supplier-portal actors in the audit
        # trail; the ``extra`` payload carries supplier_id + token_id
        # so the event is still fully attributable.
        actor_user_id=None,
        target_type="purchase_order",
        target_id=str(po_id),
        request=request,
        extra={
            "supplier_id": str(supplier_id),
            "token_id": str(token_id),
        },
    )
    await db.commit()
    return ConfirmOut(po_id=po_id, confirmed_at=datetime.now(timezone.utc))


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _po_to_out(po: Any) -> POOut:
    return POOut(
        id=po.id,
        status=str(getattr(po.status, "value", po.status)),
        total=str(po.total),
        notes=po.notes,
        created_at=po.created_at,
        confirmed_at=po.confirmed_at,
        items=[
            POItemOut(
                id=it.id,
                product_id=it.product_id,
                quantity=it.quantity,
                unit_price=str(it.unit_price),
                line_total=str(it.line_total),
            )
            for it in po.items
        ],
    )
