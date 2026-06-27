"""Auth feature package — main auth + local auth."""
from fastapi import APIRouter
from . import auth_routes
from . import local_auth

router = APIRouter()
router.include_router(auth_routes.router)
router.include_router(local_auth.router)
from . import onboarding, settings_security, trial
router.include_router(onboarding.router)
router.include_router(settings_security.router)
router.include_router(trial.router)
