"""Billing feature package."""
from fastapi import APIRouter
from . import billing, merchant_subscriptions

router = APIRouter()
router.include_router(billing.router)
router.include_router(merchant_subscriptions.router)
