"""Inventory feature package."""
from fastapi import APIRouter
from . import inventory, inventory_audit, stock_counts, stock_transfers, auto_reorder, product_import, product_activity, product_notes, product_tags, labels, manufacturing, bom_extras, qc, kitting, landed_costs, vendor_ratings

router = APIRouter()
router.include_router(inventory.router)
router.include_router(inventory_audit.router)
router.include_router(stock_counts.router)
router.include_router(stock_transfers.router)
router.include_router(auto_reorder.router)
router.include_router(product_import.router)
router.include_router(product_activity.router)
router.include_router(product_notes.router)
router.include_router(product_tags.router)
router.include_router(labels.router)
router.include_router(manufacturing.router)
router.include_router(bom_extras.router)
router.include_router(qc.router)
router.include_router(kitting.router)
router.include_router(landed_costs.router)
router.include_router(vendor_ratings.router)
from . import return_pickups, warehouse_activity, warehouse_notes, warehouse_tags
router.include_router(return_pickups.router)
router.include_router(warehouse_activity.router)
router.include_router(warehouse_notes.router)
router.include_router(warehouse_tags.router)
