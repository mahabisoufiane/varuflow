"""Petty Cash router — track small cash transactions with running balance."""
import logging
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from .petty_cash_models import PettyCashTransaction
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)
router = APIRouter(tags=["petty-cash"], dependencies=[Depends(require_module("finance"))])


class PettyCashIn(BaseModel):
    txn_date: date
    txn_type: str  # deposit | withdrawal
    amount: float
    description: str | None = None
    receipt_url: str | None = None
    currency: str = "SEK"


@router.get("/api/petty-cash")
async def list_petty_cash(
    from_date: date | None = None,
    to_date: date | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(PettyCashTransaction).where(PettyCashTransaction.org_id == org_id)
        if from_date:
            q = q.where(PettyCashTransaction.txn_date >= from_date)
        if to_date:
            q = q.where(PettyCashTransaction.txn_date <= to_date)
        rows = (await db.execute(q.order_by(PettyCashTransaction.txn_date.desc(), PettyCashTransaction.created_at.desc()))).scalars().all()
        return [_txn_dict(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_petty_cash failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/petty-cash/balance")
async def petty_cash_balance(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        deposits = (await db.execute(
            select(func.coalesce(func.sum(PettyCashTransaction.amount), 0))
            .where(PettyCashTransaction.org_id == org_id, PettyCashTransaction.txn_type == "deposit")
        )).scalar()
        withdrawals = (await db.execute(
            select(func.coalesce(func.sum(PettyCashTransaction.amount), 0))
            .where(PettyCashTransaction.org_id == org_id, PettyCashTransaction.txn_type == "withdrawal")
        )).scalar()
        balance = float(deposits) - float(withdrawals)
        return {"balance": balance, "total_deposits": float(deposits), "total_withdrawals": float(withdrawals)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"petty_cash_balance failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/petty-cash", status_code=201)
async def create_petty_cash(body: PettyCashIn, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        if body.txn_type not in ("deposit", "withdrawal"):
            raise HTTPException(status_code=422, detail="txn_type must be deposit or withdrawal")
        rec = PettyCashTransaction(
            org_id=org_id,
            created_by=member.get("user_id"),
            txn_date=body.txn_date,
            txn_type=body.txn_type,
            amount=Decimal(str(body.amount)),
            description=body.description,
            receipt_url=body.receipt_url,
            currency=body.currency,
        )
        db.add(rec)
        await db.commit()
        await db.refresh(rec)
        return _txn_dict(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_petty_cash failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/petty-cash/{txn_id}", status_code=204)
async def delete_petty_cash(txn_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        role = member.get("role", "MEMBER")
        if role not in ("OWNER", "ADMIN"):
            raise HTTPException(status_code=403, detail="Only managers can delete petty cash entries")
        rec = (await db.execute(select(PettyCashTransaction).where(PettyCashTransaction.id == txn_id, PettyCashTransaction.org_id == org_id))).scalar_one_or_none()
        if not rec:
            raise HTTPException(status_code=404, detail="Not found")
        await db.delete(rec)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_petty_cash failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


def _txn_dict(r: PettyCashTransaction) -> dict:
    return {
        "id": str(r.id),
        "txn_date": r.txn_date.isoformat(),
        "txn_type": r.txn_type,
        "amount": float(r.amount),
        "description": r.description,
        "receipt_url": r.receipt_url,
        "currency": r.currency,
        "created_by": str(r.created_by) if r.created_by else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
