"""Notifications feature package."""
from fastapi import APIRouter
from . import notifications, notification_channels, notification_prefs, notification_bundles, messaging, unified_inbox, message_translation, smart_replies, sms_outbox, announcements, voice_reports

router = APIRouter()
router.include_router(notifications.router)
router.include_router(notification_channels.router)
router.include_router(notification_prefs.router)
router.include_router(notification_bundles.router)
router.include_router(messaging.router)
router.include_router(unified_inbox.router)
router.include_router(message_translation.router)
router.include_router(smart_replies.router)
router.include_router(sms_outbox.router)
router.include_router(announcements.router)
router.include_router(voice_reports.router)
from . import live_chat, lock_screen_alerts, recurring_reminders
router.include_router(live_chat.router)
router.include_router(lock_screen_alerts.router)
router.include_router(recurring_reminders.router)
