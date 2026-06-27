"""Bookings feature package."""
from fastapi import APIRouter
from . import bookings, booking_subscriptions, booking_waitlist, booking_capacity, group_bookings, scheduling, meeting_links

router = APIRouter()
router.include_router(bookings.router)
router.include_router(booking_subscriptions.router)
router.include_router(booking_waitlist.router)
router.include_router(booking_capacity.router)
router.include_router(group_bookings.router)
router.include_router(scheduling.router)
router.include_router(meeting_links.router)
from . import after_sales, insurance_addons, live_tracking, photo_updates, service_status, service_timeline, video_consultations
router.include_router(after_sales.router)
router.include_router(insurance_addons.router)
router.include_router(live_tracking.router)
router.include_router(photo_updates.router)
router.include_router(service_status.router)
router.include_router(service_timeline.router)
router.include_router(video_consultations.router)
router.include_router(after_sales.public_router)
