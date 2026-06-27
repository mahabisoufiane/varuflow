"""Model barrel — imports every SQLAlchemy model so Alembic can detect them.

IMPORTANT: Import from concrete model files directly, NEVER via feature
__init__.py packages, to avoid circular imports through the router layer.
"""
from app.database import Base  # noqa: F401

# ── Core / org (not moved) ────────────────────────────────────────────────────
from app.features.auth.organization import *  # noqa: F401, F403
from app.features.auth.modules import *  # noqa: F401, F403
from app.features.portal.model_branding import *  # noqa: F401, F403
from app.features.marketing.model_waitlist import *  # noqa: F401, F403
from app.features.portal.idempotency import *  # noqa: F401, F403
from app.features.ai.ai_snooze import *  # noqa: F401, F403
from app.features.invoicing.dunning import *  # noqa: F401, F403
from app.features.auth.model_onboarding import *  # noqa: F401, F403
from app.features.ai.ai_usage import *  # noqa: F401, F403
from app.features.portal.status import *  # noqa: F401, F403
from app.features.purchases.payable_invoice import *  # noqa: F401, F403
from app.features.settings.model_currencies import *  # noqa: F401, F403
from app.features.mobile.mobile_field import *  # noqa: F401, F403
from app.features.corporate.model_multi_entity import *  # noqa: F401, F403
from app.features.corporate.cross_entity_roles import *  # noqa: F401, F403
from app.features.compliance.governance import *  # noqa: F401, F403
from app.features.corporate.investor import *  # noqa: F401, F403
from app.features.corporate.model_cap_table import *  # noqa: F401, F403
from app.features.analytics.board_pack import *  # noqa: F401, F403
from app.features.corporate.model_data_room import *  # noqa: F401, F403
from app.features.bookings.video_consultation import *  # noqa: F401, F403
from app.features.bookings.service_status_alert import *  # noqa: F401, F403
from app.features.bookings.model_service_timeline import *  # noqa: F401, F403
from app.features.bookings.model_live_tracking import *  # noqa: F401, F403
from app.features.bookings.service_photo_update import *  # noqa: F401, F403
from app.features.ai.ai_recommendation import *  # noqa: F401, F403
from app.features.notifications.model_live_chat import *  # noqa: F401, F403
from app.features.ai.model_chatbot import *  # noqa: F401, F403
from app.features.ai.model_knowledge_base import *  # noqa: F401, F403
from app.features.inventory.return_pickup import *  # noqa: F401, F403
from app.features.bookings.service_insurance_addon import *  # noqa: F401, F403
from app.features.invoicing.dispute import *  # noqa: F401, F403
from app.features.notifications.sentiment_log import *  # noqa: F401, F403
from app.features.mobile.mobile_kpi_config import *  # noqa: F401, F403
from app.features.notifications.push_notification_token import *  # noqa: F401, F403
from app.features.ai.ai_product_description import *  # noqa: F401, F403
from app.features.ai.model_ai_email_draft import *  # noqa: F401, F403
from app.features.ai.ai_photo_tag import *  # noqa: F401, F403
from app.features.ai.ai_price_suggestion import *  # noqa: F401, F403
from app.features.ai.ai_customer_persona import *  # noqa: F401, F403
from app.features.portal.search_history import *  # noqa: F401, F403
from app.features.settings.location_timezone import *  # noqa: F401, F403
from app.features.mobile.home_screen_widget import *  # noqa: F401, F403
from app.features.mobile.watch_session import *  # noqa: F401, F403
from app.features.ai.voice_shortcut import *  # noqa: F401, F403
from app.features.notifications.lock_screen_alert import *  # noqa: F401, F403
from app.features.marketing.upsell import *  # noqa: F401, F403
from app.features.billing.grace_period import *  # noqa: F401, F403
from app.features.auth.trial_sequences import *  # noqa: F401, F403
from app.features.analytics.growth import *  # noqa: F401, F403
from app.models.operator_referrals import *  # noqa: F401, F403
from app.features.expenses.model_accountant_forwarding import *  # noqa: F401, F403
from app.features.invoicing.receipt_export import *  # noqa: F401, F403
from app.features.invoicing.quote_comparison import *  # noqa: F401, F403
from app.features.customers.staff_portfolio_photo import *  # noqa: F401, F403
from app.features.bookings.model_after_sales import *  # noqa: F401, F403
from app.features.notifications.messaging import *  # noqa: F401, F403
from app.features.billing.model_merchant_subscriptions import *  # noqa: F401, F403
from app.features.invoicing.model_quotes import *  # noqa: F401, F403
from app.features.notifications.email_templates import *  # noqa: F401, F403
from app.features.notifications.recurring_reminder import *  # noqa: F401, F403
from app.features.customers.family_group import *  # noqa: F401, F403

# ── Features — import concrete model files directly (not __init__.py) ─────────

# auth
from app.features.auth.models import *  # noqa: F401, F403

# invoicing
from app.features.invoicing.models import *  # noqa: F401, F403

# pos
from app.features.pos.models import *  # noqa: F401, F403
from app.features.pos.pos_quick_button import *  # noqa: F401, F403

# hr
from app.features.hr.models import *  # noqa: F401, F403
from app.features.hr.hr_onboarding_training import *  # noqa: F401, F403
from app.features.hr.leave_requests import *  # noqa: F401, F403
from app.features.hr.leave_entitlement import *  # noqa: F401, F403
from app.features.hr.shift import *  # noqa: F401, F403
from app.features.hr.shift_swap import *  # noqa: F401, F403
from app.features.hr.payroll_models import *  # noqa: F401, F403
from app.features.hr.timesheet import *  # noqa: F401, F403
from app.features.hr.time_entries import *  # noqa: F401, F403
from app.features.hr.performance import *  # noqa: F401, F403
from app.features.hr.employee_contracts import *  # noqa: F401, F403
from app.features.hr.commissions_models import *  # noqa: F401, F403
from app.features.hr.training_management import *  # noqa: F401, F403

# expenses
from app.features.expenses.models import *  # noqa: F401, F403
from app.features.expenses.expense_budget import *  # noqa: F401, F403
from app.features.expenses.expense_note import *  # noqa: F401, F403
from app.features.expenses.expense_report import *  # noqa: F401, F403
from app.features.expenses.expense_tag import *  # noqa: F401, F403
from app.features.expenses.mileage_log import *  # noqa: F401, F403
from app.features.expenses.fixed_assets_models import *  # noqa: F401, F403
from app.features.expenses.petty_cash_models import *  # noqa: F401, F403
from app.features.expenses.recurring_expense import *  # noqa: F401, F403

# inventory
from app.features.inventory.models import *  # noqa: F401, F403
from app.features.inventory.bom import *  # noqa: F401, F403
from app.features.inventory.stock_count import *  # noqa: F401, F403
from app.features.inventory.stock_transfers_models import *  # noqa: F401, F403
from app.features.inventory.quality_control import *  # noqa: F401, F403
from app.features.inventory.kits import *  # noqa: F401, F403
from app.features.inventory.landed_costs_models import *  # noqa: F401, F403
from app.features.inventory.auto_reorder_models import *  # noqa: F401, F403
from app.features.inventory.work_orders_mfg import *  # noqa: F401, F403
from app.features.inventory.workflow_rules import *  # noqa: F401, F403
from app.features.inventory.import_job import *  # noqa: F401, F403
from app.features.inventory.product_note import *  # noqa: F401, F403
from app.features.inventory.product_tag import *  # noqa: F401, F403
from app.features.inventory.vendor_ratings_models import *  # noqa: F401, F403
from app.features.inventory.product_variant import *  # noqa: F401, F403
from app.features.inventory.product_waitlist import *  # noqa: F401, F403

# customers
from app.features.customers.models import *  # noqa: F401, F403
from app.features.customers.customer_app import *  # noqa: F401, F403
from app.features.customers.customer_address import *  # noqa: F401, F403
from app.features.customers.customer_api_key import *  # noqa: F401, F403
from app.features.customers.customer_chat_models import *  # noqa: F401, F403
from app.features.customers.customer_contact import *  # noqa: F401, F403
from app.features.customers.customer_history_models import *  # noqa: F401, F403
from app.features.customers.customer_important_date import *  # noqa: F401, F403
from app.features.customers.customer_note import *  # noqa: F401, F403
from app.features.customers.customer_notification_pref import *  # noqa: F401, F403
from app.features.customers.customer_org_member import *  # noqa: F401, F403
from app.features.customers.customer_preferences_models import *  # noqa: F401, F403
from app.features.customers.customer_price_override import *  # noqa: F401, F403
from app.features.customers.customer_staff_note import *  # noqa: F401, F403
from app.features.customers.customer_tag import *  # noqa: F401, F403
from app.features.customers.customer_voice_note import *  # noqa: F401, F403
from app.features.customers.customer_webhook import *  # noqa: F401, F403
from app.features.customers.lead_forms_models import *  # noqa: F401, F403
from app.features.customers.leads_models import *  # noqa: F401, F403
from app.features.customers.segments_models import *  # noqa: F401, F403
from app.features.customers.custom_field import *  # noqa: F401, F403
from app.features.customers.tag import *  # noqa: F401, F403

# purchases
from app.features.purchases.models import *  # noqa: F401, F403
from app.features.purchases.buyer_purchase_order import *  # noqa: F401, F403
from app.features.purchases.purchase_order_note import *  # noqa: F401, F403
from app.features.purchases.purchase_order_tag import *  # noqa: F401, F403
from app.features.purchases.supplier_contact import *  # noqa: F401, F403
from app.features.purchases.supplier_credit_note import *  # noqa: F401, F403
from app.features.purchases.supplier_lead_time import *  # noqa: F401, F403
from app.features.purchases.supplier_note import *  # noqa: F401, F403
from app.features.purchases.supplier_portal_models import *  # noqa: F401, F403
from app.features.purchases.supplier_sustainability_models import *  # noqa: F401, F403
from app.features.purchases.supplier_tag import *  # noqa: F401, F403

# analytics
from app.features.analytics.models import *  # noqa: F401, F403
from app.features.analytics.cashflow_models import *  # noqa: F401, F403
from app.features.analytics.cashflow_scenario import *  # noqa: F401, F403
from app.features.analytics.anomaly import *  # noqa: F401, F403
from app.features.analytics.anomaly_notification import *  # noqa: F401, F403
from app.features.analytics.budget_models import *  # noqa: F401, F403
from app.features.analytics.ceo import *  # noqa: F401, F403
from app.features.analytics.vat_period import *  # noqa: F401, F403
from app.features.analytics.voice_report_query import *  # noqa: F401, F403
from app.features.analytics.statement_request import *  # noqa: F401, F403
from app.features.analytics.report_builder_models import *  # noqa: F401, F403
from app.features.analytics.dashboard_builder_models import *  # noqa: F401, F403
from app.features.analytics.zatca_models import *  # noqa: F401, F403
from app.features.analytics.accounting_models import *  # noqa: F401, F403
from app.features.analytics.accounting_partners import *  # noqa: F401, F403

# bookings
from app.features.bookings.models import *  # noqa: F401, F403
from app.features.bookings.booking_slots_config import *  # noqa: F401, F403
from app.features.bookings.booking_subscription import *  # noqa: F401, F403
from app.features.bookings.booking_waitlist_models import *  # noqa: F401, F403
from app.features.bookings.meeting_links_models import *  # noqa: F401, F403
from app.features.bookings.group_booking import *  # noqa: F401, F403

# loyalty
from app.features.loyalty.models import *  # noqa: F401, F403
from app.features.loyalty.loyalty_streak import *  # noqa: F401, F403
from app.features.loyalty.membership_tier import *  # noqa: F401, F403
from app.features.loyalty.birthday_voucher import *  # noqa: F401, F403
from app.features.loyalty.gift_cards_models import *  # noqa: F401, F403
from app.features.loyalty.referral import *  # noqa: F401, F403
from app.features.loyalty.referral_tracking import *  # noqa: F401, F403
from app.features.loyalty.wallet_pass import *  # noqa: F401, F403
from app.features.loyalty.wallet_payment_session import *  # noqa: F401, F403
from app.features.loyalty.saved_payment_method import *  # noqa: F401, F403
from app.features.loyalty.achievement import *  # noqa: F401, F403

# projects
from app.features.projects.models import *  # noqa: F401, F403
from app.features.projects.tasks_models import *  # noqa: F401, F403
from app.features.projects.job_cards_models import *  # noqa: F401, F403
from app.features.projects.work_management_models import *  # noqa: F401, F403
from app.features.projects.okr_models import *  # noqa: F401, F403
from app.features.projects.checklist import *  # noqa: F401, F403
from app.features.projects.decision_log_models import *  # noqa: F401, F403
from app.features.projects.sop import *  # noqa: F401, F403
from app.features.projects.documents_models import *  # noqa: F401, F403

# storefront
from app.features.storefront.models import *  # noqa: F401, F403
from app.features.storefront.local_payments_models import *  # noqa: F401, F403
from app.features.storefront.gcc_payments_models import *  # noqa: F401, F403
from app.features.storefront.payment_options_models import *  # noqa: F401, F403

# marketing
from app.features.marketing.models import *  # noqa: F401, F403
from app.features.marketing.email_sequences_models import *  # noqa: F401, F403
from app.features.marketing.marketing_attribution_models import *  # noqa: F401, F403
from app.features.marketing.marketing_broadcast import *  # noqa: F401, F403
from app.features.marketing.ab_test import *  # noqa: F401, F403
from app.features.marketing.landing_page import *  # noqa: F401, F403
from app.features.marketing.nps_models import *  # noqa: F401, F403
from app.features.marketing.reviews_models import *  # noqa: F401, F403
from app.features.marketing.merchant_customer_review import *  # noqa: F401, F403
from app.features.marketing.service_review import *  # noqa: F401, F403

# compliance
from app.features.compliance.models import *  # noqa: F401, F403
from app.features.compliance.consent import *  # noqa: F401, F403
from app.features.compliance.esign_models import *  # noqa: F401, F403
from app.features.compliance.whistleblower_models import *  # noqa: F401, F403
from app.features.compliance.conflict_register import *  # noqa: F401, F403
from app.features.compliance.regulatory_calendar_models import *  # noqa: F401, F403
from app.features.compliance.risk import *  # noqa: F401, F403
from app.features.compliance.insurance_models import *  # noqa: F401, F403
from app.features.compliance.carbon_models import *  # noqa: F401, F403
from app.features.compliance.esg_models import *  # noqa: F401, F403
from app.features.compliance.identity_verification_models import *  # noqa: F401, F403
from app.features.compliance.staff_background_check import *  # noqa: F401, F403
from app.features.compliance.staff_credential import *  # noqa: F401, F403
from app.features.compliance.audit_models import *  # noqa: F401, F403

# integrations
from app.features.integrations.models import *  # noqa: F401, F403
from app.features.integrations.zapier import *  # noqa: F401, F403
from app.features.integrations.bank_feed_models import *  # noqa: F401, F403
from app.features.integrations.merchant_calendar_sync_models import *  # noqa: F401, F403
from app.features.integrations.calendar_sync_models import *  # noqa: F401, F403
from app.features.integrations.webhook import *  # noqa: F401, F403
from app.features.integrations.developer_models import *  # noqa: F401, F403

# notifications
from app.features.notifications.models import *  # noqa: F401, F403
from app.features.notifications.notification_bundle import *  # noqa: F401, F403
from app.features.notifications.unified_message import *  # noqa: F401, F403
from app.features.notifications.message_translation_models import *  # noqa: F401, F403
from app.features.notifications.smart_reply_log import *  # noqa: F401, F403
from app.features.notifications.sms_outbox_models import *  # noqa: F401, F403
from app.features.notifications.announcements_models import *  # noqa: F401, F403

# portal
from app.features.portal.models import *  # noqa: F401, F403
from app.features.portal.portal_notification_prefs import *  # noqa: F401, F403
from app.features.portal.portal_session import *  # noqa: F401, F403
