"""Marketing feature package."""
from fastapi import APIRouter
from . import campaigns, email_sequences, email_templates, marketing_attribution, marketing_broadcasts, ab_testing, landing_pages, nps, reviews, merchant_reviews, service_reviews, sentiment_analysis

router = APIRouter()
router.include_router(campaigns.router)
router.include_router(email_sequences.router)
router.include_router(email_templates.router)
router.include_router(marketing_attribution.router)
router.include_router(marketing_broadcasts.router)
router.include_router(ab_testing.router)
router.include_router(landing_pages.router)
router.include_router(nps.router)
router.include_router(reviews.router)
router.include_router(merchant_reviews.router)
router.include_router(service_reviews.router)
router.include_router(sentiment_analysis.router)
from . import operator_referrals, partner_program, upsells, waitlist
router.include_router(operator_referrals.router)
router.include_router(partner_program.router)
router.include_router(upsells.router)
router.include_router(waitlist.router)
