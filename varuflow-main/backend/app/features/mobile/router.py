"""Mobile feature package."""
from fastapi import APIRouter
from . import (
    home_screen_widgets, mobile_routes, mobile_signatures,
    mobile_voice_notes, voice_notes, watch_sessions,
)

router = APIRouter()
router.include_router(home_screen_widgets.router)
router.include_router(mobile_routes.router)
router.include_router(mobile_signatures.router)
router.include_router(mobile_voice_notes.router)
router.include_router(voice_notes.router)
router.include_router(watch_sessions.router)
