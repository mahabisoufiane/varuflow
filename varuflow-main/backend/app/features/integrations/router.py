"""Integrations feature package."""
from fastapi import APIRouter
from . import integrations, visma_sync, zapier_connect, zapier_connector, bank_feed, merchant_calendar_sync, calendar_sync, data_import, webhooks, developer

router = APIRouter()
router.include_router(integrations.router)
router.include_router(visma_sync.router)
router.include_router(zapier_connect.router)
router.include_router(zapier_connector.router)
router.include_router(bank_feed.router)
router.include_router(merchant_calendar_sync.router)
router.include_router(calendar_sync.router)
router.include_router(data_import.router)
router.include_router(webhooks.router)
router.include_router(developer.router)
from . import accounting_partners
router.include_router(accounting_partners.router)
