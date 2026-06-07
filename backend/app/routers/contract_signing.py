"""Contract digital signing endpoint.

Adds POST /api/contracts/{contract_id}/sign to the existing contracts router.
A separate router prefix is used to avoid circular imports with the main
contracts.py module; both are registered in main.py.

Signing flow:
  1. User confirms their name and submits
  2. Server computes SHA256 of: contract body + signer_name + signer_email + signed_at ISO
  3. Stores signer_name, signer_email, signature_hash, signed_at on the contract
  4. Status moves DRAFT → ACTIVE (if currently DRAFT)

This constitutes an electronic signature under EU eIDAS Level 1 (Simple
Electronic Signature) — the signer's identity claim + intent to sign is recorded
with a tamper-evident hash.
"""
import hashlib
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.customer_contract import ContractStatus, CustomerContract
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)
router = APIRouter(tags=["contract-signing"], dependencies=[Depends(require_module("invoicing"))])


class SignBody(BaseModel):
    signer_name: str          # typed full name — serves as the signature
    signer_email: str         # confirms identity
    confirm_text: str = ""    # optional "I agree" confirmation text


@router.post("/api/contracts/{contract_id}/sign")
async def sign_contract(
    contract_id: str,
    body: SignBody,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """
    Digitally sign a contract in-app. Any authenticated org member can sign;
    the signer's name and email are recorded alongside a tamper-evident hash.
    """
    try:
        org_id = member["org_id"]
        contract = (await db.execute(
            select(CustomerContract).where(
                CustomerContract.id == contract_id,
                CustomerContract.org_id == org_id,
            )
        )).scalar_one_or_none()

        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        if contract.status in (ContractStatus.TERMINATED, ContractStatus.EXPIRED):
            raise HTTPException(status_code=409, detail=f"Cannot sign a {contract.status.value.lower()} contract")
        if contract.signed_at:
            raise HTTPException(status_code=409, detail="Contract is already signed")

        if not body.signer_name.strip():
            raise HTTPException(status_code=422, detail="signer_name is required")

        now = datetime.now(timezone.utc)

        # Compute tamper-evident hash
        body_text = contract.body or ""
        sig_input = f"{body_text}|{body.signer_name.strip()}|{body.signer_email.strip()}|{now.isoformat()}"
        signature_hash = hashlib.sha256(sig_input.encode()).hexdigest()

        contract.signer_name = body.signer_name.strip()
        contract.signer_email = body.signer_email.strip()
        contract.signature_hash = signature_hash
        contract.signed_at = now

        # DRAFT contracts move to ACTIVE upon signing
        if contract.status == ContractStatus.DRAFT:
            contract.status = ContractStatus.ACTIVE

        await db.commit()
        await db.refresh(contract)

        return {
            "id": str(contract.id),
            "title": contract.title,
            "status": contract.status.value,
            "signer_name": contract.signer_name,
            "signer_email": contract.signer_email,
            "signature_hash": contract.signature_hash,
            "signed_at": contract.signed_at.isoformat(),
            "message": "Contract signed successfully. A tamper-evident record has been created.",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"sign_contract failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/contracts/{contract_id}/signature")
async def get_signature(
    contract_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return the signature record for a signed contract."""
    try:
        org_id = member["org_id"]
        contract = (await db.execute(
            select(CustomerContract).where(
                CustomerContract.id == contract_id, CustomerContract.org_id == org_id
            )
        )).scalar_one_or_none()
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        if not contract.signed_at:
            return {"signed": False}
        return {
            "signed": True,
            "signer_name": contract.signer_name,
            "signer_email": contract.signer_email,
            "signed_at": contract.signed_at.isoformat(),
            "signature_hash": contract.signature_hash,
            "verification_note": (
                "This signature was created using a Simple Electronic Signature (SES) "
                "under EU eIDAS. The hash covers the contract body, signer identity, "
                "and timestamp."
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_signature failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")
