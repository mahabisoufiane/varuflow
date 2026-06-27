"""Hr feature package."""
from fastapi import APIRouter
from . import hr_employees, hr_employee_onboarding, hr_leave, hr_org_chart, hr_reviews, hr_time, hr_timesheets, hr_training, shifts, payroll, commissions

router = APIRouter()
router.include_router(hr_employees.router)
router.include_router(hr_employee_onboarding.router)
router.include_router(hr_leave.router)
router.include_router(hr_org_chart.router)
router.include_router(hr_reviews.router)
router.include_router(hr_time.router)
router.include_router(hr_timesheets.router)
router.include_router(hr_training.router)
router.include_router(shifts.router)
router.include_router(payroll.router)
router.include_router(commissions.router)
from . import approval_chains, staff_notes, team
router.include_router(approval_chains.router)
router.include_router(staff_notes.router)
router.include_router(team.router)
