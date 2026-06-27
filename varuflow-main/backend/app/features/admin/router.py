"""Admin feature package."""
from fastapi import APIRouter
from . import admin, dev_tools, sandbox, trial_admin

router = APIRouter()
router.include_router(admin.router)
router.include_router(dev_tools.router)
router.include_router(sandbox.router)
router.include_router(trial_admin.router)
