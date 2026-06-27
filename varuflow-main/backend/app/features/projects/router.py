"""Projects feature package."""
from fastapi import APIRouter
from . import projects, tasks, job_cards, work_management, okr, contracts, contract_signing, documents, sop_library, checklists, decision_log

router = APIRouter()
router.include_router(projects.router)
router.include_router(tasks.router)
router.include_router(job_cards.router)
router.include_router(work_management.router)
router.include_router(okr.router)
router.include_router(contracts.router)
router.include_router(contract_signing.router)
router.include_router(documents.router)
router.include_router(sop_library.router)
router.include_router(checklists.router)
router.include_router(decision_log.router)
