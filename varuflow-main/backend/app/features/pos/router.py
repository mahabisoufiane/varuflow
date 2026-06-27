"""Pos feature package."""
from fastapi import APIRouter
from . import pos, pos_auth, buyer_pos, pos_quick_buttons

router = APIRouter()
router.include_router(pos.router)
router.include_router(pos_auth.router)
router.include_router(buyer_pos.router)
router.include_router(pos_quick_buttons.router)
from . import mobile_terminal
router.include_router(mobile_terminal.router)
