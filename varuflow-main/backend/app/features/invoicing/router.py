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
# Only the four core modules use RELATIVE paths and belong under the
# /api/invoicing prefix.
router.include_router(_customers_router)
router.include_router(_invoices_router)
router.include_router(_payments_router)
router.include_router(_payment_links_router)

# Every other sub-module declares its own ABSOLUTE prefix (/api/credit-notes,
# /api/recurring, /api/quotes, …) and its own require_module(...) dependency.
# Nesting them under this prefixed aggregate doubled every path
# (/api/invoicing/api/recurring — the frontend 404'd across credit notes,
# disputes, recurring, quotes, …) and stacked an extra module gate onto the
# public token/cron endpoints. They are exported on `standalone_router`
# (no prefix, no extra deps) which main.py mounts at app level.
from . import credit_notes, disputes, invoice_activity, invoice_notes, invoice_tags, invoice_templates, quote_comparisons, quotes, receipt_exports, recurring

standalone_router = APIRouter()
standalone_router.include_router(credit_notes.router)
standalone_router.include_router(disputes.router)
standalone_router.include_router(invoice_activity.router)
standalone_router.include_router(invoice_notes.router)
standalone_router.include_router(invoice_tags.router)
standalone_router.include_router(invoice_templates.router)
standalone_router.include_router(quote_comparisons.router)
standalone_router.include_router(receipt_exports.router)
standalone_router.include_router(recurring.router)
standalone_router.include_router(recurring.public_router)
standalone_router.include_router(quotes.router)
standalone_router.include_router(quotes.public_router)
