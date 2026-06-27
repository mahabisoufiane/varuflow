"""Corporate feature package."""
from fastapi import APIRouter
from . import cap_table, data_room, franchise, investor_updates, multi_entity

router = APIRouter()
router.include_router(cap_table.router)
router.include_router(data_room.router)
router.include_router(franchise.router)
router.include_router(investor_updates.router)
router.include_router(multi_entity.router)
