"""Purchases feature package."""
from fastapi import APIRouter
from . import purchase_requests, purchase_order_notes, purchase_order_tags, purchase_order_activity, supplier_portal, supplier_activity, supplier_contacts, supplier_notes, supplier_statements, supplier_tags, supplier_credit_notes, supplier_sustainability, reconciliation

router = APIRouter()
router.include_router(purchase_requests.router)
router.include_router(purchase_order_notes.router)
router.include_router(purchase_order_tags.router)
router.include_router(purchase_order_activity.router)
router.include_router(supplier_portal.router)
router.include_router(supplier_activity.router)
router.include_router(supplier_contacts.router)
router.include_router(supplier_notes.router)
router.include_router(supplier_statements.router)
router.include_router(supplier_tags.router)
router.include_router(supplier_credit_notes.router)
router.include_router(supplier_sustainability.router)
router.include_router(reconciliation.router)
