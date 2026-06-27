"""Portal feature package."""
from fastapi import APIRouter
from . import portal, portal_admin

router = APIRouter()
router.include_router(portal.router)
router.include_router(portal_admin.router)
from . import branding, saved_filters, search
router.include_router(branding.router)
router.include_router(saved_filters.router)
router.include_router(search.router)
