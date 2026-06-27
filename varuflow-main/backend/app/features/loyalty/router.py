"""Loyalty feature package."""
from fastapi import APIRouter
from . import loyalty, loyalty_streaks, membership_tiers, achievements, birthday_vouchers, gift_cards, referrals, referrals_sprint9, wallet_payments, wallet_passes, saved_payment_methods

router = APIRouter()
router.include_router(loyalty.router)
router.include_router(loyalty_streaks.router)
router.include_router(membership_tiers.router)
router.include_router(achievements.router)
router.include_router(birthday_vouchers.router)
router.include_router(gift_cards.router)
router.include_router(referrals.router)
router.include_router(referrals_sprint9.router)
router.include_router(wallet_payments.router)
router.include_router(wallet_passes.router)
router.include_router(saved_payment_methods.router)
