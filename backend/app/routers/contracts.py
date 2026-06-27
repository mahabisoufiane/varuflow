"""Customer contracts router (Item 66).

Endpoints under ``/api/contracts``:

    GET    ""                       list / filter
    POST   ""                       create DRAFT
    GET    /{contract_id}            detail
    PATCH  /{contract_id}            edit DRAFT / ACTIVE
    DELETE /{contract_id}            delete DRAFT only
    POST   /{contract_id}/activate   DRAFT → ACTIVE
    POST   /{contract_id}/terminate  ACTIVE → TERMINATED with reason
    POST   /{contract_id}/renew      extend end_date by auto_renew_months

Status transitions are enforced by ``svc.assert_transition``. A
terminated or expired contract is immutable.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.customer_contract import ContractStatus, CustomerContract
from app.models.invoicing import Customer
from app.services import customer_contract as svc
from app.services.audit import log_action

router = APIRouter(prefix="/api/contracts", tags=["contracts"])

log = logging.getLogger(__name__)


class ContractCreate(BaseModel):
    customer_id:       uuid.UUID
    title:             str
    start_date:        date
    end_date:          date | None = None
    value_amount:      Decimal = Decimal("0")
    currency:          str = "SEK"
    body:              str | None = None
    auto_renew_months: int | None = None


class ContractUpdate(BaseModel):
    title:             str | None = None
    start_date:        date | None = None
    end_date:          date | None = None
    value_amount:      Decimal | None = None
    currency:          str | None = None
    body:              str | None = None
    auto_renew_months: int | None = None


class ContractOut(BaseModel):
    id:                 uuid.UUID
    customer_id:        uuid.UUID
    title:              str
    status:             ContractStatus
    start_date:         date
    end_date:           date | None
    value_amount:       Decimal
    currency:           str
    body:               str | None
    auto_renew_months:  int | None
    signed_at:          datetime | None
    terminated_at:      datetime | None
    termination_reason: str | None
    created_at:         datetime
    updated_at:         datetime


class TerminateBody(BaseModel):
    reason: str


async def _load(
    db: AsyncSession, *, contract_id: uuid.UUID, org_id: uuid.UUID
) -> CustomerContract:
    row = await db.get(CustomerContract, contract_id)
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Contract not found")
    return row


@router.get("", response_model=list[ContractOut])
async def list_contracts(
    customer_id: uuid.UUID | None = Query(default=None),
    status_:     str | None = Query(default=None, alias="status"),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _user, member = ctx
    stmt = select(CustomerContract).where(
        CustomerContract.org_id == member.org_id
    )
    if customer_id is not None:
        stmt = stmt.where(CustomerContract.customer_id == customer_id)
    if status_ is not None:
        if status_ not in svc.ALLOWED_STATUSES:
            raise HTTPException(status_code=400, detail="invalid status")
        stmt = stmt.where(CustomerContract.status == ContractStatus(status_))
    stmt = stmt.order_by(CustomerContract.created_at.desc())
    rows = (await db.scalars(stmt)).all()
    return list(rows)


@router.post("", response_model=ContractOut, status_code=status.HTTP_201_CREATED)
async def create_contract(
    body: ContractCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    # Customer must belong to the caller's org.
    customer = await db.scalar(
        select(Customer).where(
            Customer.id == body.customer_id, Customer.org_id == member.org_id
        )
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    try:
        title = svc.validate_title(body.title)
        dates = svc.validate_dates(body.start_date, body.end_date)
        value = svc.validate_value_amount(body.value_amount)
        currency = svc.validate_currency(body.currency)
        body_text = svc.validate_body(body.body)
        renew = svc.validate_renew_months(body.auto_renew_months)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    row = CustomerContract(
        org_id=member.org_id,
        customer_id=body.customer_id,
        title=title,
        status=ContractStatus.DRAFT,
        start_date=dates.start,
        end_date=dates.end,
        value_amount=value,
        currency=currency,
        body=body_text,
        auto_renew_months=renew,
    )
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="contract.created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="contract",
        target_id=str(row.id),
        request=request,
        extra={"customer_id": str(body.customer_id)},
    )
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/{contract_id}", response_model=ContractOut)
async def get_contract(
    contract_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _user, member = ctx
    return await _load(db, contract_id=contract_id, org_id=member.org_id)


@router.patch("/{contract_id}", response_model=ContractOut)
async def update_contract(
    contract_id: uuid.UUID,
    body: ContractUpdate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, contract_id=contract_id, org_id=member.org_id)
    if row.status in (ContractStatus.EXPIRED, ContractStatus.TERMINATED):
        raise HTTPException(
            status_code=409, detail="cannot edit finalised contract"
        )

    changed: list[str] = []
    try:
        if body.title is not None:
            row.title = svc.validate_title(body.title); changed.append("title")
        # Dates: validate as a pair if either moves.
        new_start = body.start_date if body.start_date is not None else row.start_date
        new_end = body.end_date if body.end_date is not None else row.end_date
        if body.start_date is not None or body.end_date is not None:
            dates = svc.validate_dates(new_start, new_end)
            if body.start_date is not None:
                row.start_date = dates.start; changed.append("start_date")
            if body.end_date is not None:
                row.end_date = dates.end; changed.append("end_date")
        if body.value_amount is not None:
            row.value_amount = svc.validate_value_amount(body.value_amount)
            changed.append("value_amount")
        if body.currency is not None:
            row.currency = svc.validate_currency(body.currency)
            changed.append("currency")
        if body.body is not None:
            row.body = svc.validate_body(body.body); changed.append("body")
        if body.auto_renew_months is not None:
            row.auto_renew_months = svc.validate_renew_months(body.auto_renew_months)
            changed.append("auto_renew_months")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if changed:
        row.updated_at = datetime.now(timezone.utc)
        await log_action(
            db,
            action="contract.updated",
            org_id=member.org_id,
            actor_user_id=user["user_id"],
            target_type="contract",
            target_id=str(row.id),
            request=request,
            extra={"fields": changed},
        )
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contract(
    contract_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, contract_id=contract_id, org_id=member.org_id)
    if row.status != ContractStatus.DRAFT:
        raise HTTPException(
            status_code=409, detail="can only delete DRAFT contracts"
        )
    await db.delete(row)
    await log_action(
        db,
        action="contract.deleted",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="contract",
        target_id=str(contract_id),
        request=request,
        extra={},
    )
    await db.commit()
    return None


@router.post("/{contract_id}/activate", response_model=ContractOut)
async def activate_contract(
    contract_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, contract_id=contract_id, org_id=member.org_id)
    try:
        svc.assert_transition(row.status.value, "ACTIVE")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    row.status = ContractStatus.ACTIVE
    row.signed_at = datetime.now(timezone.utc)
    row.updated_at = row.signed_at
    await log_action(
        db,
        action="contract.activated",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="contract",
        target_id=str(row.id),
        request=request,
        extra={},
    )
    await db.commit()
    await db.refresh(row)
    return row


@router.post("/{contract_id}/terminate", response_model=ContractOut)
async def terminate_contract(
    contract_id: uuid.UUID,
    body: TerminateBody,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, contract_id=contract_id, org_id=member.org_id)
    try:
        svc.assert_transition(row.status.value, "TERMINATED")
        reason = svc.validate_reason(body.reason)
    except ValueError as e:
        raise HTTPException(
            status_code=409 if "transition" in str(e) else 400, detail=str(e)
        )
    now = datetime.now(timezone.utc)
    row.status = ContractStatus.TERMINATED
    row.terminated_at = now
    row.termination_reason = reason
    row.updated_at = now
    await log_action(
        db,
        action="contract.terminated",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="contract",
        target_id=str(row.id),
        request=request,
        extra={"reason": reason[:120]},
    )
    await db.commit()
    await db.refresh(row)
    return row


@router.post("/{contract_id}/renew", response_model=ContractOut)
async def renew_contract(
    contract_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await _load(db, contract_id=contract_id, org_id=member.org_id)
    if row.status != ContractStatus.ACTIVE:
        raise HTTPException(
            status_code=409, detail="can only renew ACTIVE contracts"
        )
    if row.end_date is None or row.auto_renew_months is None:
        raise HTTPException(
            status_code=409,
            detail="contract has no end_date or auto_renew_months configured",
        )
    new_end = svc.next_renewal_end(row.end_date, row.auto_renew_months)
    old_end = row.end_date
    row.end_date = new_end
    row.updated_at = datetime.now(timezone.utc)
    await log_action(
        db,
        action="contract.renewed",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="contract",
        target_id=str(row.id),
        request=request,
        extra={
            "old_end": old_end.isoformat(),
            "new_end": new_end.isoformat(),
            "months": row.auto_renew_months,
        },
    )
    await db.commit()
    await db.refresh(row)
    return row
