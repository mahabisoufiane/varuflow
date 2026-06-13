from app.database import Base  # noqa: F401

# Import all models so Alembic can detect them
from app.models.organization import Organization, OrganizationMember  # noqa: F401
from app.models.inventory import (  # noqa: F401
    Product,
    ProductBatch,
    Supplier,
    Warehouse,
    StockLevel,
    StockMovement,
    PurchaseOrder,
    PurchaseOrderItem,
)
from app.models.invoicing import (  # noqa: F401
    Customer,
    Invoice,
    InvoiceLineItem,
    Payment,
    RecurringInvoice,
)
from app.models.pos import PosSession, PosSale, PosSaleItem  # noqa: F401
from app.models.waitlist import Waitlist  # noqa: F401
from app.models.audit import AuditLogEntry  # noqa: F401
from app.models.idempotency import IdempotencyKey  # noqa: F401
from app.models.ai_snooze import AiCardSnooze  # noqa: F401
from app.models.supplier_lead_time import SupplierLeadTime  # noqa: F401
from app.models.dunning import DunningEvent  # noqa: F401
from app.models.portal_session import PortalSession  # noqa: F401
from app.models.customer_price_override import CustomerPriceOverride  # noqa: F401
from app.models.notifications import DeviceToken  # noqa: F401
from app.models.onboarding import OnboardingProgress  # noqa: F401
from app.models.ai_usage import DailyAiUsage  # noqa: F401
from app.models.webhook import WebhookEndpoint, WebhookDelivery  # noqa: F401
from app.models.status import HealthCheck, StatusIncident  # noqa: F401
from app.models.stock_count import StockCount, StockCountItem, StockCountStatus  # noqa: F401
from app.models.auto_reorder import AutoReorderRun  # noqa: F401
from app.models.payable_invoice import PayableInvoice  # noqa: F401
from app.models.bookings import (  # noqa: F401
    Appointment,
    AppointmentReminder,
    Service,
    Staff,
)
from app.models.commissions import (  # noqa: F401
    CommissionEntry,
    CommissionRule,
    CommissionRun,
)
from app.models.gift_cards import (  # noqa: F401
    BundleRedemption,
    GiftCard,
    ServiceBundle,
)
from app.models.currencies import ExchangeRate  # noqa: F401
from app.models.loyalty import (  # noqa: F401
    LoyaltyAccount,
    LoyaltyProgram,
    LoyaltyTransaction,
)
from app.models.supplier_portal import SupplierPortalToken  # noqa: F401
from app.models.stock_transfers import (  # noqa: F401
    StockTransfer,
    StockTransferItem,
    StockTransferStatus,
)
from app.models.segments import (  # noqa: F401
    Segment,
    SegmentMember,
    SegmentType,
)
from app.models.campaigns import (  # noqa: F401
    Campaign,
    CampaignSend,
    CampaignSendStatus,
    CampaignStatus,
)
from app.models.accounting import (  # noqa: F401
    AccountType,
    ChartOfAccount,
    JournalEntry,
    JournalLine,
)
from app.models.fixed_assets import FixedAsset, AssetDepreciation  # noqa: F401
from app.models.payroll import PayrollRun, PayrollEntry  # noqa: F401
from app.models.budget import Budget, BudgetLine  # noqa: F401
from app.models.bank_feed import BankAccount, BankTransaction  # noqa: F401
from app.models.ecommerce import (  # noqa: F401
    Storefront,
    OnlineOrder,
    OnlineOrderItem,
    CartSession,
)
from app.models.crm import Deal, DealActivity, DealStage  # noqa: F401
from app.models.lead_forms import LeadForm, LeadFormSubmission  # noqa: F401
from app.models.email_sequences import (  # noqa: F401
    EmailSequence,
    EmailSequenceStep,
    EmailSequenceEnrollment,
)
from app.models.meeting_links import MeetingLink  # noqa: F401
from app.models.hr import EmployeeProfile, EmployeeEmergencyContact  # noqa: F401
from app.models.employee_contracts import EmployeeContract  # noqa: F401
from app.models.leave_requests import LeaveRequest  # noqa: F401
from app.models.leave_entitlement import LeaveEntitlement, PublicHoliday  # noqa: F401
from app.models.time_entries import TimeEntry  # noqa: F401
from app.models.performance import PerformanceCycle, PerformanceReview  # noqa: F401
from app.models.bom import BomHeader, BomLine  # noqa: F401
from app.models.work_orders_mfg import WorkOrder, WorkOrderMaterialLine, WorkOrderLabourLine  # noqa: F401
from app.models.quality_control import QcChecklist, QcInspection  # noqa: F401
from app.models.projects import Project, ProjectTask, ProjectMilestone, ProjectExpense, ProjectTimeEntry, ProjectRetainer  # noqa: F401
from app.models.workflow_rules import WorkflowRule  # noqa: F401
from app.models.zatca import ZatcaInvoice  # noqa: F401
from app.models.gcc_payments import GccPaymentSession  # noqa: F401
from app.models.integration_config import IntegrationConfig, NotificationChannel  # noqa: F401
from app.models.mobile_field import DeliveryRoute, RouteStop, DigitalSignature, StripeTerminalSession, VoiceNote  # noqa: F401
from app.models.multi_entity import IntercompanyTransfer, EliminationEntry, FranchiseAgreement, RoyaltyBilling, FranchiseCatalogPush  # noqa: F401
from app.models.compliance import FieldMaskingRule, PentestReport  # noqa: F401
from app.models.bi import DashboardConfig, CustomReport, ScheduledReport  # noqa: F401
from app.models.ceo import KpiGoal, Scenario  # noqa: F401
from app.models.growth import PartnerProgram, Partner, PartnerDeal, PricingExperiment, MarketExpansionChecklist  # noqa: F401
from app.models.accounting_partners import AccountingFirmPartner, AccountingPartnerReferral  # noqa: F401
from app.models.operator_referrals import OperatorReferral  # noqa: F401
from app.models.governance import ApprovalRule, ApprovalRequest, PolicyDocument, ApprovalDelegate  # noqa: F401
from app.models.hr_onboarding_training import EmployeeOnboardingTask, EmployeeTrainingRecord  # noqa: F401
from app.models.work_management import WmTask, WmAnnouncement, MeetingNote, OpsWorkOrder, Ticket  # noqa: F401
from app.models.shift_swap import ShiftSwapRequest  # noqa: F401
from app.models.shift import Shift, ShiftPunch, RosterPublication  # noqa: F401
from app.models.timesheet import Timesheet, TimesheetLine  # noqa: F401
from app.models.training_management import MandatoryTrainingRequirement, TrainingRequest  # noqa: F401
from app.models.portal_notification_prefs import PortalNotificationPreference  # noqa: F401
from app.models.purchase_request import PurchaseRequest, PurchaseRequestItem  # noqa: F401
from app.models.petty_cash import PettyCashTransaction  # noqa: F401
from app.models.portal_communication import (  # noqa: F401
    PortalChatMessage,
    OrderTimelineEvent,
    InvoiceViewEvent,
    PortalTicket,
    PortalTicketReply,
    FriendlyReminder,
)
from app.models.quotes import Quote, QuoteLineItem  # noqa: F401
from app.models.payment_options import (  # noqa: F401
    PaymentPlan,
    PaymentPlanInstalment,
    EarlyPaymentDiscount,
    DepositRequest,
    PortalTermsAcceptance,
    NdaAgreement,
)
from app.models.after_sales import (  # noqa: F401
    ReturnRequest,
    WarrantyRecord,
    SatisfactionSurvey,
    UpsellSuggestion,
)
from app.models.messaging import StaffMessage, StaffMessageRead  # noqa: F401
from app.models.leads import Lead, LeadScoreEvent  # noqa: F401
from app.models.cashflow import CashFlowAdjustment  # noqa: F401
from app.models.vat_period import VatPeriod  # noqa: F401
from app.models.tasks import Task, TaskComment  # noqa: F401
from app.models.announcements import Announcement, AnnouncementRead  # noqa: F401
from app.models.job_cards import JobCard, JobCardPart, JobCardLabour, JobCardPhoto  # noqa: F401
from app.models.email_templates import EmailTemplate, EmailTemplateSend  # noqa: F401
from app.models.sms_outbox import SmsMessage, SmsOptOut  # noqa: F401
from app.models.local_payments import LocalPaymentConfig, LocalPaymentSession  # noqa: F401
from app.models.merchant_subscriptions import MerchantSubscriptionPlan, MerchantSubscription  # noqa: F401
from app.models.landed_costs import LandedCostCharge, LandedCostLine  # noqa: F401
from app.models.vendor_ratings import VendorManualRating, VendorRatingCache  # noqa: F401
from app.models.kits import KitDefinition, KitComponent, KitAssembly  # noqa: F401
from app.models.dashboard_builder import DashboardLayout, ScheduledDashboard  # noqa: F401
from app.models.report_builder import SavedReport, RbScheduledReport  # noqa: F401
from app.models.anomaly import AnomalyFinding  # noqa: F401
from app.models.cashflow_scenario import CashFlowScenario  # noqa: F401
from app.models.esign import ESignRequest, ESignSignatory, ESignAuditEntry  # noqa: F401
from app.models.consent import ConsentRecord, ConsentAuditLog, DsarRequest  # noqa: F401
from app.models.import_job import ImportJob  # noqa: F401
from app.models.cross_entity_roles import MultiEntityRole  # noqa: F401
from app.models.okr import OkrObjective, OkrKeyResult  # noqa: F401
from app.models.risk import RiskItem  # noqa: F401
from app.models.insurance import InsurancePolicy, InsuranceClaim  # noqa: F401
from app.models.regulatory_calendar import RegulatoryEvent  # noqa: F401
from app.models.whistleblower import WhistleblowerReport  # noqa: F401
from app.models.conflict_register import ConflictDeclaration  # noqa: F401
from app.models.carbon import CarbonEntry  # noqa: F401
from app.models.esg import EsgReport  # noqa: F401
from app.models.supplier_sustainability import SupplierSustainabilityRating  # noqa: F401
from app.models.investor import InvestorUpdate, InvestorUpdateRecipient  # noqa: F401
from app.models.cap_table import Shareholder, ShareClass, Shareholding, DilutionScenario  # noqa: F401
from app.models.board_pack import BoardPack  # noqa: F401
from app.models.data_room import DataRoomFolder, DataRoomDocument, DataRoomShare  # noqa: F401
from app.models.marketing_attribution import AttributionSource, AttributionEvent  # noqa: F401
from app.models.ab_test import AbTest, AbTestVariant  # noqa: F401
from app.models.landing_page import LandingPage  # noqa: F401
from app.models.marketing_broadcast import MarketingBroadcast  # noqa: F401
from app.models.nps import NpsSurvey, SubscriptionHealthScore  # noqa: F401
from app.models.sop import SopDocument, SopVersion  # noqa: F401
from app.models.checklist import ChecklistTemplate, ChecklistTemplateItem, ChecklistRun, ChecklistRunItem  # noqa: F401
from app.models.recurring_reminder import RecurringReminder, ReminderOccurrence  # noqa: F401
from app.models.decision_log import DecisionEntry  # noqa: F401
from app.models.family_group import FamilyGroup, FamilyMember  # noqa: F401
from app.models.booking_subscription import BookingSubscription  # noqa: F401
from app.models.group_booking import GroupBooking, GroupBookingParticipant  # noqa: F401
from app.models.booking_waitlist import BookingWaitlistEntry  # noqa: F401
from app.models.wallet_pass import WalletPass  # noqa: F401
from app.models.customer_app import CustomerAppPushToken, CustomerAppConfig  # noqa: F401
from app.models.customer_chat import CustomerChatThread, CustomerChatMessage  # noqa: F401
from app.models.video_consultation import VideoConsultation  # noqa: F401
from app.models.customer_voice_note import CustomerVoiceNote  # noqa: F401
from app.models.customer_notification_pref import CustomerNotificationPref  # noqa: F401
from app.models.service_status_alert import ServiceStatusAlert  # noqa: F401
from app.models.service_timeline import ServiceTimeline, ServiceTimelineEvent  # noqa: F401
from app.models.live_tracking import LiveTrackingSession  # noqa: F401
from app.models.service_photo_update import ServicePhotoUpdate  # noqa: F401
from app.models.customer_history import CustomerHistoryEvent  # noqa: F401
from app.models.customer_preferences import CustomerPreference  # noqa: F401
from app.models.ai_recommendation import AiRecommendation  # noqa: F401
from app.models.customer_important_date import CustomerImportantDate  # noqa: F401
from app.models.saved_payment_method import SavedPaymentMethod  # noqa: F401
from app.models.customer_staff_note import CustomerStaffNote  # noqa: F401
from app.models.membership_tier import MembershipTier, CustomerMembership  # noqa: F401
from app.models.achievement import Achievement, CustomerAchievement  # noqa: F401
from app.models.birthday_voucher import BirthdayVoucher  # noqa: F401
from app.models.referral_tracking import ReferralTracking  # noqa: F401
from app.models.loyalty_streak import LoyaltyStreak  # noqa: F401
from app.models.customer_address import CustomerAddress  # noqa: F401
from app.models.calendar_sync import CalendarSyncToken  # noqa: F401
from app.models.accountant_forwarding import AccountantForwarding  # noqa: F401
from app.models.receipt_export import ReceiptExport  # noqa: F401
from app.models.wallet_payment_session import WalletPaymentSession  # noqa: F401
from app.models.buyer_purchase_order import BuyerPurchaseOrder, BuyerPoLineItem  # noqa: F401
from app.models.customer_org_member import CustomerOrgMember, BuyerOrderApproval  # noqa: F401
from app.models.quote_comparison import QuoteComparison  # noqa: F401
from app.models.service_review import ServiceReview  # noqa: F401
from app.models.staff_credential import StaffCredential  # noqa: F401
from app.models.booking_slots_config import BookingSlotsConfig  # noqa: F401
from app.models.staff_portfolio_photo import StaffPortfolioPhoto  # noqa: F401
from app.models.live_chat import LiveChatSession, LiveChatMessage  # noqa: F401
from app.models.chatbot import ChatbotConfig, ChatbotConversation  # noqa: F401
from app.models.knowledge_base import KbCategory, KbArticle  # noqa: F401
from app.models.return_pickup import ReturnPickupRequest  # noqa: F401
from app.models.identity_verification import IdentityVerification  # noqa: F401
from app.models.staff_background_check import StaffBackgroundCheck  # noqa: F401
from app.models.service_insurance_addon import ServiceInsuranceAddon, BookingInsurancePurchase  # noqa: F401
from app.models.dispute import Dispute, DisputeMessage  # noqa: F401
from app.models.merchant_customer_review import MerchantCustomerReview  # noqa: F401
from app.models.unified_message import UnifiedInboxThread, UnifiedMessage  # noqa: F401
from app.models.message_translation import MessageTranslation  # noqa: F401
from app.models.smart_reply_log import SmartReplyLog  # noqa: F401
from app.models.sentiment_log import ConversationSentimentLog  # noqa: F401
from app.models.statement_request import StatementRequest  # noqa: F401
from app.models.mobile_kpi_config import MobileKpiConfig  # noqa: F401
from app.models.push_notification_token import PushNotificationToken  # noqa: F401
from app.models.voice_report_query import VoiceReportQuery  # noqa: F401
from app.models.anomaly_notification import AnomalyNotification  # noqa: F401
from app.models.ai_product_description import AiProductDescription  # noqa: F401
from app.models.ai_email_draft import AiEmailDraft  # noqa: F401
from app.models.ai_photo_tag import AiPhotoTag  # noqa: F401
from app.models.ai_price_suggestion import AiPriceSuggestion  # noqa: F401
from app.models.ai_customer_persona import AiCustomerPersona  # noqa: F401
from app.models.merchant_calendar_sync import MerchantCalendarSync  # noqa: F401
from app.models.zapier import ZapierHook, ZapierEventLog  # noqa: F401
from app.models.customer_webhook import CustomerWebhook, CustomerWebhookDelivery  # noqa: F401
from app.models.customer_api_key import CustomerApiKey  # noqa: F401
from app.models.search_history import SearchHistory  # noqa: F401
from app.models.notification_bundle import NotificationBundleConfig  # noqa: F401
from app.models.location_timezone import OrgLocationTimezone  # noqa: F401
from app.models.home_screen_widget import HomeScreenWidget, WidgetDataSnapshot  # noqa: F401
from app.models.watch_session import WatchSession  # noqa: F401
from app.models.voice_shortcut import VoiceShortcut  # noqa: F401
from app.models.lock_screen_alert import LockScreenAlert  # noqa: F401
from app.models.upsell import UpsellEvent  # noqa: F401
from app.models.grace_period import SubscriptionGracePeriod, GracePeriodStatus  # noqa: F401
from app.models.trial_sequences import (  # noqa: F401
    TrialSequence,
    TrialSequenceStep,
    TrialEnrollment,
    TrialEmailSend,
)
