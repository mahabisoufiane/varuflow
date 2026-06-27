"""Invoicing routes: customers."""
import logging
import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from .models import (
    Customer,
)
from .schemas import (
    CustomerCreate,
    CustomerOut,
    CustomerUpdate,
)

from ._shared import (
    _org,
)

log = logging.getLogger(__name__)
router = APIRouter()


# ── Customers ─────────────────────────────────────────────────────────────────

@router.get("/customers", response_model=list[CustomerOut])
async def list_customers(
    search: str | None = Query(None),
    is_active: bool | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        q = select(Customer).where(Customer.org_id == org_id)
        if search:
            like = f"%{search}%"
            q = q.where(
                Customer.company_name.ilike(like) | Customer.email.ilike(like)
            )
        if is_active is not None:
            q = q.where(Customer.is_active == is_active)
        q = q.order_by(Customer.company_name).limit(limit).offset(offset)
        result = await db.execute(q)
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_customers failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/customers", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
async def create_customer(
    body: CustomerCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        customer = Customer(
            org_id=org_id,
            company_name=body.company_name,
            org_number=body.org_number,
            vat_number=body.vat_number,
            email=body.email,
            phone=body.phone,
            address=body.address,
            payment_terms_days=body.payment_terms_days,
        )
        db.add(customer)
        await db.commit()
        await db.refresh(customer)
        return customer
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_customer failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/customers/{customer_id}", response_model=CustomerOut)
async def get_customer(
    customer_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        c = await db.scalar(
            select(Customer).where(Customer.id == customer_id, Customer.org_id == org_id)
        )
        if not c:
            raise HTTPException(status_code=404, detail="Customer not found")
        return c
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_customer failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/customers/{customer_id}", response_model=CustomerOut)
async def update_customer(
    customer_id: uuid.UUID,
    body: CustomerUpdate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        c = await db.scalar(
            select(Customer).where(Customer.id == customer_id, Customer.org_id == org_id)
        )
        if not c:
            raise HTTPException(status_code=404, detail="Customer not found")
        # Partial-update semantics: only overwrite columns the client actually
        # supplied. Without exclude_unset, `CustomerUpdate`'s schema defaults
        # (payment_terms_days=30, email/phone/etc. -> None) silently overwrite
        # every unspecified field — so a PUT that only wants to rename the
        # customer wipes their contact info and resets payment terms to 30.
        _PROTECTED = {"id", "org_id", "created_at"}
        for k, v in body.model_dump(exclude_unset=True).items():
            if k not in _PROTECTED:
                setattr(c, k, v)
        await db.commit()
        await db.refresh(c)
        return c
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_customer failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/customers/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_customer(
    customer_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    c = await db.scalar(
        select(Customer).where(Customer.id == customer_id, Customer.org_id == org_id)
    )
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    c.is_active = False
    _, member = ctx
    from app.features.compliance.audit_models import AuditLogEntry as _AL
    db.add(_AL(
        org_id=org_id,
        actor_user_id=member.user_id,
        action="customer.deactivated",
        target_type="customer",
        target_id=str(customer_id),
        extra={"company_name": c.company_name, "email": c.email},
    ))
    await db.commit()


