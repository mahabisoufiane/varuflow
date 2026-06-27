"""AI feature package."""
from fastapi import APIRouter
from . import (
    ai_automation, ai_email_draft, ai_engine, ai_personas,
    ai_photo_tags, ai_pricing, ai_product_desc, ai_recommendations,
    chatbot, knowledge_base, voice_shortcuts,
)

router = APIRouter()
router.include_router(ai_automation.router)
router.include_router(ai_email_draft.router)
router.include_router(ai_engine.router)
router.include_router(ai_personas.router)
router.include_router(ai_photo_tags.router)
router.include_router(ai_pricing.router)
router.include_router(ai_product_desc.router)
router.include_router(ai_recommendations.router)
router.include_router(chatbot.router)
router.include_router(knowledge_base.router)
router.include_router(voice_shortcuts.router)
