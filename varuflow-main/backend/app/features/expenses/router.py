"""Expenses feature package."""
from fastapi import APIRouter
from . import expenses, expense_activity, expense_budgets, expense_notes, expense_reports, expense_tags, mileage_logs, petty_cash, fixed_assets, recurring_expenses

router = APIRouter()
router.include_router(expenses.router)
router.include_router(expense_activity.router)
router.include_router(expense_budgets.router)
router.include_router(expense_notes.router)
router.include_router(expense_reports.router)
router.include_router(expense_tags.router)
router.include_router(mileage_logs.router)
router.include_router(petty_cash.router)
router.include_router(fixed_assets.router)
router.include_router(recurring_expenses.router)
from . import accountant_forwarding
router.include_router(accountant_forwarding.router)
