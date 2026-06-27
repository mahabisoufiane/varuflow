"""Compliance feature package."""
from fastapi import APIRouter
from . import gdpr, gdpr_consent, compliance_audit_chain, compliance_data_residency, compliance_field_masking, compliance_pentest, esign, whistleblower, conflict_of_interest, regulatory_calendar, risk_register, insurance, carbon, esg, audit, identity_verification, background_checks, staff_credentials

router = APIRouter()
router.include_router(gdpr.router)
router.include_router(gdpr_consent.router)
router.include_router(compliance_audit_chain.router)
router.include_router(compliance_data_residency.router)
router.include_router(compliance_field_masking.router)
router.include_router(compliance_pentest.router)
router.include_router(esign.router)
router.include_router(whistleblower.router)
router.include_router(conflict_of_interest.router)
router.include_router(regulatory_calendar.router)
router.include_router(risk_register.router)
router.include_router(insurance.router)
router.include_router(carbon.router)
router.include_router(esg.router)
router.include_router(audit.router)
router.include_router(identity_verification.router)
router.include_router(background_checks.router)
router.include_router(staff_credentials.router)
from . import einvoice, policy_docs
router.include_router(einvoice.router)
router.include_router(policy_docs.router)
