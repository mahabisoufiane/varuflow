"""Settings feature package."""
from fastapi import APIRouter
from . import countries, currencies, location_timezones

router = APIRouter()
router.include_router(countries.router)
router.include_router(currencies.router)
router.include_router(location_timezones.router)
