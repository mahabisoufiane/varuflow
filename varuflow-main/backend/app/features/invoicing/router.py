"""Invoicing feature package — customers, invoices, payments, payment links.

Split from a single 1857-line module into route sub-modules + shared helpers.
The public `router` (mounted at /api/invoicing) and the document-generator
helpers re-exported below preserve the previous import surface exactly:
`from app.routers import invoicing; invoicing.router` and
`from app.routers.invoicing import _generate_invoice_pdf` both still resolve.
"""
from fastapi import APIRouter, Depends

from app.middleware.plan_check import require_module

# Re-exported for portal / gdpr / einvoice / recurring_send.
from ._shared import (  # noqa: F401
    _generate_ehf_xml,
    _generate_invoice_pdf,
    _generate_peppol_xml,
    _invoice_number,
)
from .customers import router as _customers_router
from .invoices import router as _invoices_router
from .payment_links import router as _payment_links_router
from .payments import router as _payments_router

router = APIRouter(
    prefix="/api/invoicing",
    tags=["invoicing"],
    dependencies=[Depends(require_module("invoicing"))],
)
router.include_router(_customers_router)
router.include_router(_invoices_router)
router.include_router(_payments_router)
router.include_router(_payment_links_router)
from . import credit_notes, disputes, invoice_activity, invoice_notes, invoice_tags, invoice_templates, quote_comparisons, quotes, receipt_exports, recurring
router.include_router(credit_notes.router)
router.include_router(disputes.router)
router.include_router(invoice_activity.router)
router.include_router(invoice_notes.router)
router.include_router(invoice_tags.router)
router.include_router(invoice_templates.router)
router.include_router(quote_comparisons.router)
# NOTE: quotes.router / quotes.public_router are mounted at APP level in
# main.py, NOT here. quotes.py declares absolute "/api/quotes/..." paths (the
# frontend and public quote-view tokens depend on them); nesting them under
# this aggregate (a) doubled every path to /api/invoicing/api/quotes and
# (b) made the public token endpoints inherit require_module("invoicing"),
# locking customers out of their own quote links.
router.include_router(receipt_exports.router)
router.include_router(recurring.router)
router.include_router(recurring.public_router)
