"""Storefront feature package."""
from fastapi import APIRouter
from . import storefront, online_orders, shop_config, shopify_sync, payment_options, local_payments, gcc_payments, open_banking

router = APIRouter()
router.include_router(storefront.router)
router.include_router(online_orders.router)
router.include_router(shop_config.router)
router.include_router(shopify_sync.router)
router.include_router(payment_options.router)
router.include_router(local_payments.router)
router.include_router(gcc_payments.router)
router.include_router(open_banking.router)
